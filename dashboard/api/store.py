"""Thread-safe, bounded in-memory runs with atomic snapshot/event publication."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from .config import Settings
from .errors import DemoError
from .models import ErrorInfo, InputInfo, RunEvent, RunSnapshot, TaskSnapshot


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
    workbook_path: Path | None = None
    source_pdf: Path | None = None


@dataclass
class UploadedTender:
    """Keep a bounded, temporary PDF selection independent of analysis retries."""

    path: Path
    display_name: str
    created: float = field(default_factory=monotonic)


class RunStore:
    """Serialize concurrent worker updates and retain replay until run expiry."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock = RLock()
        self.records: dict[str, Record] = {}
        self.keys: dict[str, str] = {}
        self.active: str | None = None
        self.uploads: dict[str, UploadedTender] = {}

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
        retained = {record.snapshot.input.id for record in self.records.values()}
        for input_id, upload in list(self.uploads.items()):
            if (
                input_id not in retained
                and monotonic() - upload.created >= self.settings.retention_seconds
            ):
                upload.path.unlink(missing_ok=True)
                del self.uploads[input_id]

    def add_upload(self, content: bytes, display_name: str) -> str:
        """Store validated bytes under a generated name rather than a client path."""
        with self.lock:
            self._prune()
            if len(self.uploads) >= self.settings.max_uploads:
                raise DemoError(
                    "UPLOAD_BUSY", "Upload capacity is full. Try again later.", 429
                )
            input_id = str(uuid4())
            directory = self.settings.output_root / "uploads"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{input_id}.pdf"
            path.write_bytes(content)
            self.uploads[input_id] = UploadedTender(path, display_name)
            return input_id

    def input_pdf(self, input_id: str) -> Path:
        """Resolve only the configured tender or a retained generated upload ID."""
        with self.lock:
            self._prune()
            if input_id == "sample-tender":
                try:
                    path = self.settings.sample_pdf()
                    if path.is_file() and path.stat().st_size > 0:
                        return path
                except OSError:
                    pass
                raise DemoError(
                    "INPUT_UNAVAILABLE", "The sample tender is unavailable.", 503
                )
            upload = self.uploads.get(input_id)
            if upload is None or not upload.path.is_file():
                raise DemoError(
                    "INVALID_INPUT", "This upload expired. Upload your PDF again.", 422
                )
            return upload.path

    def prune(self) -> None:
        """Expire stale keys before deciding whether a start is an idempotent retry."""
        with self.lock:
            self._prune()

    def create(
        self, key: str, input_id: str = "sample-tender"
    ) -> tuple[RunSnapshot, bool]:
        """Atomically deduplicate starts before enforcing single-run admission."""
        with self.lock:
            self._prune()
            if key in self.keys:
                existing = self.records[self.keys[key]].snapshot
                if existing.input.id != input_id:
                    raise DemoError(
                        "INPUT_CONFLICT",
                        "This request key belongs to a different tender.",
                        409,
                    )
                return existing.model_copy(deep=True), False
            if self.active:
                raise DemoError(
                    "RUN_BUSY",
                    "An analysis is already running. Wait for it to finish.",
                    409,
                )
            run_id = str(uuid4())
            source = self.input_pdf(input_id) if input_id != "sample-tender" else None
            name = self.uploads[input_id].display_name if source else "tender.pdf"
            snapshot = RunSnapshot(
                run_id=run_id, input=InputInfo(id=input_id, display_name=name)
            )
            self.records[run_id] = Record(snapshot, key, source_pdf=source)
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
                "documents_total",
                "requirements_count",
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
                if kind == "stage.completed" and fields.get("stage") == "classify":
                    snap.metrics.final_requirements = fields.get("data", {}).get(
                        "requirements_count"
                    )
                self._append(record, kind, **fields)
                return
            self._append(record, kind, **fields)

    def _start_task(self, record: Record, task: TaskSnapshot) -> None:
        """Timestamp actual entry rather than treating scheduled tasks as running."""
        task.status, task.started_at = "running", utc_now()
        record.task_starts[task.id] = monotonic()

    def download_path(self, run_id: str) -> Path:
        """Expose only the workbook produced for this completed run."""
        with self.lock:
            record = self._get(run_id)
            path = record.workbook_path
            if (
                record.snapshot.status != "completed"
                or path is None
                or not path.is_file()
            ):
                raise DemoError(
                    "WORKBOOK_UNAVAILABLE",
                    "The Excel matrix is not ready for download.",
                    404,
                )
            return path

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
                path = Path((output or {}).get("workbook_path", "")).resolve()
                expected = (
                    self.settings.output_root / run_id / "compliance_matrix.xlsx"
                ).resolve()
                if path != expected or not path.is_file():
                    raise ValueError(
                        "The run did not create its Excel compliance matrix."
                    )
                record.workbook_path = path
                snap.output.excel_url = f"/api/runs/{run_id}/compliance-matrix.xlsx"
                snap.metrics.final_requirements = (output or {}).get(
                    "requirements_count"
                )
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
                else "Excel compliance matrix is ready to download.",
                data={"code": error.code} if error else {},
            )
            self.active = None
            self._prune()
