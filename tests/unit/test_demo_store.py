"""The live run store exposes only a completed run's Excel workbook."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dashboard.api.config import Settings
from dashboard.api.errors import DemoError
from dashboard.api.models import ErrorInfo
from dashboard.api.store import RunStore


def workbook(settings: Settings, run_id: str) -> dict[str, str | int]:
    """Create the exact per-run artifact the API is allowed to serve."""
    path = settings.output_root / run_id / "compliance_matrix.xlsx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"xlsx")
    return {"workbook_path": str(path), "requirements_count": 18}


def test_admission_retention_and_download_boundary(tmp_path: Path) -> None:
    settings = Settings(output_root=tmp_path, max_terminal_runs=1)
    store = RunStore(settings)
    first, created = store.create("a")
    assert created and store.create("a")[0].run_id == first.run_id
    with pytest.raises(DemoError, match="already running"):
        store.create("b")
    with pytest.raises(DemoError, match="not ready"):
        store.download_path(first.run_id)
    store.finish(first.run_id, output=workbook(settings, first.run_id))
    assert store.download_path(first.run_id).read_bytes() == b"xlsx"
    assert store.snapshot(first.run_id).output.excel_url.endswith(
        "compliance-matrix.xlsx"
    )
    second, _ = store.create("b")
    store.finish(second.run_id, output=workbook(settings, second.run_id))
    with pytest.raises(DemoError, match="expired"):
        store.snapshot(first.run_id)


def test_concurrent_document_events_and_final_counts(tmp_path: Path) -> None:
    settings = Settings(output_root=tmp_path)
    store = RunStore(settings)
    run_id = store.create("one")[0].run_id
    store.observe(run_id, "run.started", summary="started")
    store.observe(run_id, "stage.started", stage="extract")
    store.observe(
        run_id,
        "inputs.prepared",
        data={"documents_total": 20},
        workers=[
            {"id": f"doc-{i}", "stage": "extract", "label": f"Document {i}"}
            for i in range(20)
        ],
    )

    def worker(i: int) -> None:
        store.observe(run_id, "worker.started", stage="extract", worker_id=f"doc-{i}")
        store.observe(
            run_id,
            "worker.completed",
            stage="extract",
            worker_id=f"doc-{i}",
            data={"findings_count": 2, "secret": "private"},
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(worker, range(20)))
    store.observe(run_id, "stage.completed", stage="extract")
    store.finish(run_id, output=workbook(settings, run_id))
    events, terminal = store.replay(run_id, 0)
    assert terminal and [event.event_id for event in events] == list(
        range(1, len(events) + 1)
    )
    assert len([event for event in events if event.type == "run.completed"]) == 1
    assert all("secret" not in event.data for event in events)
    snap = store.snapshot(run_id)
    assert snap.metrics.completed_workers == 20 and snap.metrics.raw_findings == 40
    assert snap.metrics.final_requirements == 18


def test_failed_run_never_offers_download(tmp_path: Path) -> None:
    store = RunStore(Settings(output_root=tmp_path))
    run_id = store.create("one")[0].run_id
    store.observe(run_id, "run.started")
    store.observe(run_id, "stage.started", stage="extract")
    store.finish(
        run_id, error=ErrorInfo(code="PROVIDER_FAILED", message="Provider failed.")
    )
    assert store.snapshot(run_id).output.excel_url is None
    with pytest.raises(DemoError, match="not ready"):
        store.download_path(run_id)
    with pytest.raises(DemoError, match="ahead"):
        store.replay(run_id, 999)


def test_unrelated_artifact_cannot_be_attached(tmp_path: Path) -> None:
    settings = Settings(output_root=tmp_path)
    store = RunStore(settings)
    run_id = store.create("one")[0].run_id
    other = tmp_path / "elsewhere.xlsx"
    other.write_bytes(b"other")
    with pytest.raises(ValueError, match="did not create"):
        store.finish(run_id, output={"workbook_path": str(other)})
