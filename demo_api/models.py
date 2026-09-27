"""Explicit contracts for normalized events and replayable run snapshots."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from main import DecisionSupportReport, TenderAnalysis

RunStatus = Literal["queued", "running", "completed", "failed"]
TaskStatus = Literal["pending", "running", "completed", "failed", "skipped"]
Stage = Literal[
    "parse_document",
    "prepare_inputs",
    "analyze_chunk",
    "analyze_table",
    "reduce_findings",
    "generate_report",
]
STAGES = list(Stage.__args__)
EventType = Literal[
    "run.started",
    "stage.started",
    "stage.completed",
    "stage.skipped",
    "worker.started",
    "worker.completed",
    "worker.failed",
    "run.warning",
    "run.completed",
    "run.failed",
]


class StartRequest(BaseModel):
    """Only registered samples can be selected; no client paths or URLs."""

    model_config = ConfigDict(extra="forbid")
    input_id: str = Field(min_length=1, max_length=80)


class InputInfo(BaseModel):
    """Public sample identity without server filesystem details."""

    id: str = "sample-tender"
    display_name: str = "Sample tender"


class ErrorInfo(BaseModel):
    """Safe actionable failure details shared by snapshots and error events."""

    code: str
    message: str


class TaskSnapshot(BaseModel):
    """Observable worker/stage state; durations appear only when measured."""

    id: str
    stage: Stage
    label: str
    status: TaskStatus = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    findings_count: int | None = None


class Metrics(BaseModel):
    """Raw extraction counts are separate from final consolidated requirements."""

    total_chunks: int | None = None
    text_chunks: int | None = None
    tables: int | None = None
    filtered_chunks: int | None = None
    completed_workers: int = 0
    raw_findings: int = 0
    final_requirements: int | None = None


class RunOutput(BaseModel):
    """Preserve a valid analysis if subsequent report generation fails."""

    tender_analysis: TenderAnalysis | None = None
    decision_support_report: DecisionSupportReport | None = None


class RunSnapshot(BaseModel):
    """A self-contained restoration point for refresh/reconnect clients."""

    run_id: str
    status: RunStatus = "queued"
    input: InputInfo = Field(default_factory=InputInfo)
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    last_event_id: int = 0
    stages: list[TaskSnapshot] = Field(
        default_factory=lambda: [
            TaskSnapshot(id=stage, stage=stage, label=stage) for stage in STAGES
        ]
    )
    workers: list[TaskSnapshot] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    warnings: list[ErrorInfo] = Field(default_factory=list)
    output: RunOutput = Field(default_factory=RunOutput)
    error: ErrorInfo | None = None


class RunEvent(BaseModel):
    """Small frontend-safe observation; outputs and prompts never enter data."""

    event_id: int
    run_id: str
    type: EventType
    status: str
    stage: Stage | None = None
    worker_id: str | None = None
    timestamp: str
    duration_ms: int | None = None
    summary: str
    data: dict[str, str | int] = Field(default_factory=dict)
