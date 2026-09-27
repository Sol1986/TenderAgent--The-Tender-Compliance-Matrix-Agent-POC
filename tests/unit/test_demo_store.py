"""Concurrency, retention, and terminal-output integrity checks."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from demo_api.config import Settings
from demo_api.errors import DemoError
from demo_api.store import RunStore


def test_admission_idempotency_and_retention(outputs: dict[str, Any]) -> None:
    """Idempotent requests restore runs; active work cannot be evicted."""
    store = RunStore(Settings(max_terminal_runs=1))
    first, created = store.create("a")
    assert created and store.create("a")[0].run_id == first.run_id
    with pytest.raises(DemoError, match="already running"):
        store.create("b")
    store.finish(first.run_id, output=outputs)
    second, _ = store.create("b")
    store.finish(second.run_id, output=outputs)
    with pytest.raises(DemoError, match="expired"):
        store.snapshot(first.run_id)
    assert store.snapshot(second.run_id).output.tender_analysis
    store.records[second.run_id].finished -= 4000
    with pytest.raises(DemoError):
        store.snapshot(second.run_id)


def test_concurrent_updates_are_ordered_and_counted_once(
    outputs: dict[str, Any],
) -> None:
    """Real concurrent publishers cannot lose IDs, findings, or branch completion."""
    store = RunStore(Settings())
    run_id = store.create("one")[0].run_id
    store.observe(run_id, "run.started", summary="started")
    store.observe(
        run_id,
        "inputs.prepared",
        data={"text_chunks": 20, "tables": 0},
        workers=[
            {"id": f"chunk-{i}", "stage": "analyze_chunk", "label": f"Section {i}"}
            for i in range(20)
        ],
    )

    def worker(i: int) -> None:
        store.observe(
            run_id, "worker.started", stage="analyze_chunk", worker_id=f"chunk-{i}"
        )
        store.observe(
            run_id,
            "worker.completed",
            stage="analyze_chunk",
            worker_id=f"chunk-{i}",
            duration_ms=1,
            data={"findings_count": 2, "secret": "must never enter events"},
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(worker, range(20)))
    store.finish(run_id, output=outputs)
    store.finish(run_id, output=outputs)
    events, terminal = store.replay(run_id, 0)
    assert terminal and [event.event_id for event in events] == list(
        range(1, len(events) + 1)
    )
    assert len([e for e in events if e.type == "run.completed"]) == 1
    assert len([e for e in events if e.type == "stage.completed"]) == 1
    assert all("secret" not in e.data for e in events)
    snap = store.snapshot(run_id)
    assert snap.metrics.raw_findings == 40 and snap.metrics.completed_workers == 20
    assert snap.output.tender_analysis and snap.output.decision_support_report
    snap.workers.clear()
    assert len(store.snapshot(run_id).workers) == 20


def test_replay_cursor_and_partial_result(outputs: dict[str, Any]) -> None:
    """Retain validated consolidation if the final report fails."""
    from demo_api.models import ErrorInfo

    store = RunStore(Settings())
    run_id = store.create("one")[0].run_id
    store.observe(run_id, "run.started")
    store.observe(run_id, "stage.started", stage="reduce_findings")
    store.observe(
        run_id,
        "stage.completed",
        stage="reduce_findings",
        output={"final_analysis": outputs["final_analysis"]},
    )
    store.observe(run_id, "stage.started", stage="generate_report")
    store.finish(
        run_id, error=ErrorInfo(code="REPORT_FAILED", message="Report failed.")
    )
    snap = store.snapshot(run_id)
    assert snap.output.tender_analysis and snap.output.decision_support_report is None
    assert snap.status == "failed" and snap.stages[-1].status == "failed"
    assert store.replay(run_id, snap.last_event_id) == ([], True)
    assert len(store.replay(run_id, snap.last_event_id - 1)[0]) == 1
    with pytest.raises(DemoError, match="ahead"):
        store.replay(run_id, snap.last_event_id + 1)
