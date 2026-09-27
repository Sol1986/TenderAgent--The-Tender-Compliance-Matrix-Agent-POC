"""Exercise real HTTP contracts and background work without paid model calls."""

from pathlib import Path
from threading import Event
from time import monotonic, sleep
from typing import Any

import pytest
from fastapi.testclient import TestClient

from demo_api.app import create_app
from demo_api.config import Settings
from main import run_single_document_analysis


def await_terminal(client: TestClient, run_id: str) -> dict[str, Any]:
    """Bound test waiting and surface a failed worker rather than hang the suite."""
    deadline = monotonic() + 5
    while monotonic() < deadline:
        snapshot = client.get(f"/api/runs/{run_id}").json()
        if snapshot["status"] in {"completed", "failed"}:
            return snapshot
        sleep(0.01)
    raise AssertionError("Run did not terminate")


def available_sample(tmp_path: Path) -> Path:
    """Create a non-empty sample because the API checks availability before dispatch."""
    sample = tmp_path / "sample.pdf"
    sample.write_bytes(b"%PDF-test-placeholder")
    return sample


def test_start_returns_before_completion_and_replay(
    outputs: dict[str, Any], tmp_path: Path
) -> None:
    """A blocked worker proves the HTTP handler is independent of analysis."""
    entered, release = Event(), Event()

    def pipeline(observe: Any) -> dict[str, Any]:
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Test did not release worker")
        return outputs

    app = create_app(Settings(sample_path=available_sample(tmp_path)), pipeline)
    with TestClient(app) as client:
        try:
            response = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": "once"},
            )
            assert response.status_code == 202
            assert entered.wait(2) and not release.is_set()
            run_id = response.json()["run_id"]
            assert client.get(f"/api/runs/{run_id}").json()["status"] == "running"
            duplicate = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": "once"},
            )
            assert duplicate.json()["run_id"] == run_id
            busy = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": "twice"},
            )
            assert (
                busy.status_code == 409 and busy.json()["error"]["code"] == "RUN_BUSY"
            )
        finally:
            release.set()
        snapshot = await_terminal(client, run_id)
        assert snapshot["status"] == "completed"
        replay = client.get(
            f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "1"}
        )
        assert (
            "event: run.completed" in replay.text
            and "event: run.started" not in replay.text
        )
        assert "text/event-stream" in replay.headers["content-type"]
        assert (
            client.get(
                f"/api/runs/{run_id}/events?after_event_id={snapshot['last_event_id']}"
            ).text
            == ""
        )
        assert (
            client.get(f"/api/runs/{run_id}/events?after_event_id=999").status_code
            == 422
        )


def test_graph_http_outputs_and_report_failure(
    fake_model: Any, document: Any, tmp_path: Path
) -> None:
    """Drive the actual graph through HTTP, then verify partial failure state."""

    def pipeline(observe: Any) -> dict[str, Any]:
        return run_single_document_analysis(
            Path("unused"), fake_model, observe, parser=lambda _: document
        )

    settings = Settings(sample_path=available_sample(tmp_path))
    with TestClient(create_app(settings, pipeline)) as client:
        for fail in (False, True):
            fake_model.report_error = fail
            response = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": str(fail)},
            )
            snapshot = await_terminal(client, response.json()["run_id"])
            assert snapshot["status"] == ("failed" if fail else "completed")
            assert snapshot["output"]["tender_analysis"]
            assert bool(snapshot["output"]["decision_support_report"]) != fail
            assert snapshot["metrics"]["raw_findings"] == 3
            assert snapshot["metrics"]["completed_workers"] == 3
            assert snapshot["warnings"] == []
            events = client.get(response.json()["events_url"]).text
            assert "DO_NOT_EXPOSE" not in events
            assert "worker.started" in events and "worker.completed" in events


@pytest.mark.parametrize(
    "body,headers",
    [
        ({}, {}),
        ({"input_id": "../.env"}, {"Idempotency-Key": "x"}),
        ({"input_id": "sample-tender", "path": ".env"}, {"Idempotency-Key": "x"}),
    ],
)
def test_invalid_requests_are_structured(body: dict, headers: dict) -> None:
    """Reject path access and validation errors without echoing sensitive data."""
    with TestClient(create_app(Settings())) as client:
        response = client.post("/api/runs", json=body, headers=headers)
        assert response.status_code == 422
        assert set(response.json()["error"]) == {"code", "message", "request_id"}


def test_liveness_unknown_run_unavailable_sample_and_cors() -> None:
    """Health is independent of sample/provider readiness and CORS is exact."""
    with TestClient(create_app(Settings(sample_path=Path("missing.pdf")))) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/demo-inputs").json()[0]["available"] is False
        assert (
            client.get("/api/runs/missing").json()["error"]["code"] == "RUN_NOT_FOUND"
        )
        assert client.get("/api/runs/missing/events").status_code == 404
        assert (
            client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": "x"},
            ).status_code
            == 503
        )
        response = client.options(
            "/api/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Idempotency-Key",
            },
        )
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        response = client.get(
            "/health", headers={"Origin": "https://untrusted.example"}
        )
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "failure,code",
    [
        ("parser", "DOCUMENT_PROCESSING_FAILED"),
        ("provider", "PROVIDER_FAILED"),
        ("malformed", "INVALID_ANALYSIS_RESPONSE"),
    ],
)
def test_safe_failures_and_released_capacity(
    failure: str, code: str, tmp_path: Path
) -> None:
    """Failed runs emit one safe terminal event and do not keep admission locked."""

    def pipeline(observe: Any) -> dict[str, Any]:
        if failure == "parser":
            observe("stage.started", stage="parse_document")
            raise RuntimeError("PRIVATE_DOCUMENT_PATH")
        if failure == "provider":
            from httpx import Request
            from openai import APIConnectionError

            raise APIConnectionError(request=Request("POST", "https://example.invalid"))
        return {"final_analysis": {"categories": []}}

    settings = Settings(sample_path=available_sample(tmp_path))
    with TestClient(create_app(settings, pipeline)) as client:
        for key in ("first", "second"):
            start = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": key},
            )
            assert start.status_code == 202
            snapshot = await_terminal(client, start.json()["run_id"])
            assert snapshot["status"] == "failed" and snapshot["error"]["code"] == code
            events = client.get(start.json()["events_url"]).text
            assert events.count("event: run.failed\n") == 1
            assert "PRIVATE_DOCUMENT_PATH" not in events


def test_restarted_server_cannot_restore_prior_run(
    outputs: dict[str, Any], tmp_path: Path
) -> None:
    """In-memory run IDs are explicitly lost when a new server instance starts."""
    settings = Settings(sample_path=available_sample(tmp_path))
    with TestClient(create_app(settings, lambda observe: outputs)) as first:
        start = first.post(
            "/api/runs",
            json={"input_id": "sample-tender"},
            headers={"Idempotency-Key": "one"},
        )
        run_id = start.json()["run_id"]
        await_terminal(first, run_id)
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/runs/{run_id}").status_code == 404
