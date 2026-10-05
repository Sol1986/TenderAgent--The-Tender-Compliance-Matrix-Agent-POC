"""HTTP contract for live progress and the finished Excel matrix."""

from pathlib import Path
from threading import Event
from time import monotonic, sleep
from typing import Any

from fastapi.testclient import TestClient

from dashboard.api.app import create_app
from dashboard.api.config import Settings


def sample_package(tmp_path: Path) -> Path:
    package = tmp_path / "package"
    package.mkdir()
    (package / "tender.pdf").write_bytes(b"%PDF-placeholder")
    return package


def await_terminal(client: TestClient, run_id: str) -> dict[str, Any]:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        snapshot = client.get(f"/api/runs/{run_id}").json()
        if snapshot["status"] in {"completed", "failed"}:
            return snapshot
        sleep(0.01)
    raise AssertionError("Run did not terminate")


def test_live_events_and_excel_download(tmp_path: Path) -> None:
    entered, release = Event(), Event()
    settings = Settings(
        sample_path=sample_package(tmp_path), output_root=tmp_path / "runs"
    )
    app = None

    def pipeline(observe: Any) -> dict[str, Any]:
        observe("stage.started", stage="extract", summary="Extracting source PDFs.")
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Test did not release worker")
        observe("stage.completed", stage="extract", summary="Extraction complete.")
        observe("stage.started", stage="export", summary="Writing Excel matrix.")
        observe("stage.completed", stage="export", summary="Excel ready.")
        assert app is not None
        run_id = app.state.store.active
        path = settings.output_root / run_id / "compliance_matrix.xlsx"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"xlsx")
        return {"workbook_path": str(path), "requirements_count": 18}

    app = create_app(settings, pipeline)
    with TestClient(app) as client:
        assert client.get("/api/demo-inputs").json()[0]["available"] is True
        try:
            start = client.post(
                "/api/runs",
                json={"input_id": "sample-tender"},
                headers={"Idempotency-Key": "once"},
            )
            assert start.status_code == 202
            assert entered.wait(2)
            run_id = start.json()["run_id"]
            assert (
                client.get(f"/api/runs/{run_id}/compliance-matrix.xlsx").status_code
                == 404
            )
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
            assert busy.status_code == 409
        finally:
            release.set()
        snapshot = await_terminal(client, run_id)
        assert (
            snapshot["output"]["excel_url"]
            == f"/api/runs/{run_id}/compliance-matrix.xlsx"
        )
        assert snapshot["metrics"]["final_requirements"] == 18
        download = client.get(snapshot["output"]["excel_url"])
        assert download.content == b"xlsx"
        assert "spreadsheetml.sheet" in download.headers["content-type"]
        replay = client.get(
            f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "1"}
        )
        assert (
            "event: stage.started" in replay.text
            and "event: run.completed" in replay.text
        )
        assert "event: run.started" not in replay.text


def test_failure_has_no_download_and_expired_run_is_not_replayed(
    tmp_path: Path,
) -> None:
    settings = Settings(
        sample_path=sample_package(tmp_path), output_root=tmp_path / "runs"
    )

    def pipeline(observe: Any) -> dict[str, Any]:
        observe("stage.started", stage="extract")
        raise RuntimeError("PRIVATE_DOCUMENT_PATH")

    with TestClient(create_app(settings, pipeline)) as client:
        start = client.post(
            "/api/runs",
            json={"input_id": "sample-tender"},
            headers={"Idempotency-Key": "one"},
        )
        snapshot = await_terminal(client, start.json()["run_id"])
        assert (
            snapshot["status"] == "failed" and snapshot["output"]["excel_url"] is None
        )
        assert (
            client.get(
                f"/api/runs/{snapshot['run_id']}/compliance-matrix.xlsx"
            ).status_code
            == 404
        )
        assert (
            "PRIVATE_DOCUMENT_PATH" not in client.get(start.json()["events_url"]).text
        )
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/runs/{snapshot['run_id']}").status_code == 404
