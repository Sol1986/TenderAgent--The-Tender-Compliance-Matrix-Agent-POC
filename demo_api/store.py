"""Thread-safe, bounded in-memory runs with atomic snapshot/event publication."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from main_copy import DecisionSupportReport, TenderAnalysis, validate_analysis

from .config import Settings
from .errors import DemoError
from .models import ErrorInfo, RunEvent, RunSnapshot, TaskSnapshot


def utc_now() -> str:
    """Use UTC wall time for display; monotonic clocks measure duration."""
    return datetime.now(UTC).isoformat()


@dataclass
class Record:
    """Private bookkeeping separate from the public JSON contract."""

    snapshot: RunSnapshot
    key: str
    events: list[RunEvent] = field(default_factory=list)
    start: float | None = None
    finished: float | None = None
    task_starts: dict[str, float] = field(default_factory=dict)


class RunStore:
    """Serialize concurrent worker updates and retain replay until run expiry."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock = RLock()
        self.records: dict[str, Record] = {}
        self.keys: dict[str, str] = {}
        self.active: str | None = None

    def _prune(self) -> None:
        """Evict only terminal, inactive records, including their idempotency keys."""
        terminal = sorted(
            (
                record
                for record in self.records.values()
                if record.finished is not None and record.snapshot.run_id != self.active
            ),
            key=lambda record: record.finished,
        )
        excess = max(0, len(terminal) - self.settings.max_terminal_runs)
        for index, record in enumerate(terminal):
            if (
                index < excess
                or monotonic() - record.finished >= self.settings.retention_seconds
            ):
                del self.records[record.snapshot.run_id]
                self.keys.pop(record.key, None)

    def prune(self) -> None:
        """Expire stale keys before deciding whether a start is an idempotent retry."""
        with self.lock:
            self._prune()

    def create(self, key: str) -> tuple[RunSnapshot, bool]:
        """Atomically deduplicate starts before enforcing single-run admission."""
        with self.lock:
            self._prune()
            if key in self.keys:
                return self.records[self.keys[key]].snapshot.model_copy(
                    deep=True
                ), False
            if self.active:
                raise DemoError(
                    "RUN_BUSY",
                    "An analysis is already running. Wait for it to finish.",
                    409,
                )
            run_id = str(uuid4())
            snapshot = RunSnapshot(run_id=run_id)
            self.records[run_id] = Record(snapshot, key)
            self.keys[key] = run_id
            self.active = run_id
            return snapshot.model_copy(deep=True), True

    def _get(self, run_id: str) -> Record:
        """Require a retained run without exposing internal storage details."""
        self._prune()
        if run_id not in self.records:
            raise DemoError(
                "RUN_NOT_FOUND", "This run expired or the demo server restarted.", 404
            )
        return self.records[run_id]

    def snapshot(self, run_id: str) -> RunSnapshot:
        """Return an isolated restoration point so callers cannot mutate storage."""
        with self.lock:
            return self._get(run_id).snapshot.model_copy(deep=True)

    def replay(self, run_id: str, after: int) -> tuple[list[RunEvent], bool]:
        """Return newer events plus terminal state from the same locked instant."""
        with self.lock:
            record = self._get(run_id)
            if after > record.snapshot.last_event_id:
                raise DemoError(
                    "INVALID_CURSOR", "The event cursor is ahead of this run.", 422
                )
            return (
                [
                    event.model_copy(deep=True)
                    for event in record.events
                    if event.event_id > after
                ],
                record.snapshot.status in {"completed", "failed"},
            )

    def _append(self, record: Record, kind: str, **fields: Any) -> None:
        """Publish only normalized fields, never arbitrary graph state."""
        data = {
            key: value
            for key, value in (fields.get("data") or {}).items()
            if key
            in {
                "findings_count",
                "total_chunks",
                "text_chunks",
                "tables",
                "filtered_chunks",
                "code",
            }
        }
        event = RunEvent(
            event_id=len(record.events) + 1,
            run_id=record.snapshot.run_id,
            type=kind,
            status=kind.rsplit(".", 1)[-1],
            stage=fields.get("stage"),
            worker_id=fields.get("worker_id"),
            timestamp=utc_now(),
            duration_ms=fields.get("duration_ms"),
            summary=" ".join(fields.get("summary", "").split())[:600],
            data=data,
        )
        record.events.append(event)
        record.snapshot.last_event_id = event.event_id

    def observe(self, run_id: str, kind: str, **fields: Any) -> None:
        """Apply one agent observation and publish matching events atomically."""
        with self.lock:
            record = self._get(run_id)
            snap = record.snapshot
            if snap.status in {"completed", "failed"}:
                return
            if kind == "inputs.prepared":
                snap.workers = [TaskSnapshot(**worker) for worker in fields["workers"]]
                for key, value in fields["data"].items():
                    setattr(snap.metrics, key, value)
                return
            if kind == "run.started":
                record.start = monotonic()
                snap.started_at, snap.status = utc_now(), "running"
            elif kind == "run.warning":
                snap.warnings.append(
                    ErrorInfo(code=fields["data"]["code"], message=fields["summary"])
                )
            elif kind.startswith(("stage.", "worker.")):
                stage = next(item for item in snap.stages if item.id == fields["stage"])
                worker_id = fields.get("worker_id")
                task = (
                    next(item for item in snap.workers if item.id == worker_id)
                    if worker_id
                    else stage
                )
                if worker_id and kind == "worker.started" and stage.status == "pending":
                    self._start_task(record, stage)
                    self._append(
                        record,
                        "stage.started",
                        stage=stage.stage,
                        summary=f"{stage.label}: started.",
                    )
                if kind.endswith("started"):
                    self._start_task(record, task)
                else:
                    task.status = kind.rsplit(".", 1)[-1]
                    task.finished_at = utc_now()
                    task.duration_ms = fields.get("duration_ms")
                if kind == "worker.completed":
                    task.findings_count = fields["data"]["findings_count"]
                    snap.metrics.completed_workers += 1
                    snap.metrics.raw_findings += task.findings_count
                if output := fields.get("output"):
                    self._save_output(record, output)
                self._append(record, kind, **fields)
                if worker_id:
                    siblings = [
                        item for item in snap.workers if item.stage == stage.stage
                    ]
                    if all(item.status == "completed" for item in siblings):
                        stage.status, stage.finished_at = "completed", utc_now()
                        stage.duration_ms = int(
                            (monotonic() - record.task_starts[stage.id]) * 1000
                        )
                        self._append(
                            record,
                            "stage.completed",
                            stage=stage.stage,
                            duration_ms=stage.duration_ms,
                            summary=f"{stage.label}: completed.",
                        )
                return
            self._append(record, kind, **fields)

    def _start_task(self, record: Record, task: TaskSnapshot) -> None:
        """Timestamp actual entry rather than treating scheduled tasks as running."""
        task.status, task.started_at = "running", utc_now()
        record.task_starts[task.id] = monotonic()

    def _save_output(self, record: Record, output: dict[str, Any]) -> None:
        """Validate intermediate results before retaining them for failure recovery."""
        if "final_analysis" in output:
            analysis = validate_analysis(
                TenderAnalysis.model_validate(output["final_analysis"])
            )
            record.snapshot.output.tender_analysis = analysis
            record.snapshot.metrics.final_requirements = sum(
                len(c.requirements) for c in analysis.categories
            )
        if "decision_report" in output:
            record.snapshot.output.decision_support_report = (
                DecisionSupportReport.model_validate(output["decision_report"])
            )

    def finish(
        self,
        run_id: str,
        output: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        """Commit output and terminal event together; release admission on exit."""
        with self.lock:
            record = self._get(run_id)
            snap = record.snapshot
            if snap.status in {"completed", "failed"}:
                return
            if error is None:
                self._save_output(record, output or {})
                if (
                    not snap.output.tender_analysis
                    or not snap.output.decision_support_report
                ):
                    raise ValueError("The graph did not return both outputs.")
            snap.error = error
            snap.status = "failed" if error else "completed"
            record.finished = monotonic()
            snap.finished_at = utc_now()
            snap.duration_ms = (
                int((record.finished - record.start) * 1000)
                if record.start is not None
                else 0
            )
            if error:
                for task in [*snap.stages, *snap.workers]:
                    if task.status == "running":
                        task.status, task.finished_at = "failed", snap.finished_at
                        task.duration_ms = int(
                            (record.finished - record.task_starts[task.id]) * 1000
                        )
            self._append(
                record,
                f"run.{snap.status}",
                duration_ms=snap.duration_ms,
                summary=error.message
                if error
                else "Tender analysis and decision-support report are ready.",
                data={"code": error.code} if error else {},
            )
            self.active = None
            self._prune()
