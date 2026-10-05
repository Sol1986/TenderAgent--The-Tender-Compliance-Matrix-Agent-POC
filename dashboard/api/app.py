"""FastAPI composition for a local single-process tender demonstration."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .config import Settings
from .errors import DemoError, install_handlers
from .events import stream_events
from .models import RunSnapshot, StartRequest
from .runner import Pipeline, RunExecutor
from .store import RunStore


def create_app(
    settings: Settings | None = None, pipeline: Pipeline | None = None
) -> FastAPI:
    """Inject settings/pipeline in tests; do not invoke the agent at import time."""
    settings = settings or Settings.from_env()
    store = RunStore(settings)
    executor = RunExecutor(settings, store, pipeline)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await asyncio.to_thread(executor.close)

    app = FastAPI(title="Tender Agent Demo", lifespan=lifespan)
    app.state.store, app.state.executor = store, executor
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
    )
    install_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Report liveness without a paid provider request."""
        return {"status": "ok"}

    @app.get("/api/demo-inputs")
    async def inputs() -> list[dict[str, str | bool | int | None]]:
        """Advertise one configured sample, not arbitrary server files."""
        try:
            pdfs = [
                path
                for path in settings.sample_path.iterdir()
                if path.is_file() and path.suffix.casefold() == ".pdf"
            ]
            size = sum(path.stat().st_size for path in pdfs) if pdfs else None
        except OSError:
            size = None
        return [
            {
                "id": "sample-tender",
                "display_name": "Sample tender package",
                "size_bytes": size,
                "available": size is not None and size > 0,
            }
        ]

    @app.post("/api/runs", status_code=202)
    async def start(
        body: StartRequest,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
        ],
    ) -> dict[str, str]:
        """Validate the allowlisted selection and return before agent work finishes."""
        if body.input_id != "sample-tender":
            raise DemoError("INVALID_INPUT", "Select an available sample tender.", 422)
        # Validate only new starts; an idempotent retry can restore a completed
        # run even if the source file has since become unavailable.
        with store.lock:
            store.prune()
            if idempotency_key not in store.keys:
                try:
                    available = settings.sample_path.is_dir() and any(
                        path.is_file()
                        and path.suffix.casefold() == ".pdf"
                        and path.stat().st_size > 0
                        for path in settings.sample_path.iterdir()
                    )
                except OSError:
                    available = False
                if not available:
                    raise DemoError(
                        "INPUT_UNAVAILABLE",
                        "The configured sample tender is unavailable.",
                        503,
                    )
            snapshot = executor.start(idempotency_key)
        return {
            "run_id": snapshot.run_id,
            "status": snapshot.status,
            "snapshot_url": f"/api/runs/{snapshot.run_id}",
            "events_url": f"/api/runs/{snapshot.run_id}/events",
        }

    @app.get("/api/runs/{run_id}", response_model=RunSnapshot)
    async def snapshot(run_id: str) -> RunSnapshot:
        """Read current outputs and execution state without starting more work."""
        return store.snapshot(run_id)

    @app.get("/api/runs/{run_id}/compliance-matrix.xlsx")
    async def download_matrix(run_id: str) -> FileResponse:
        """Download only the validated workbook attached to this completed run."""
        return FileResponse(
            store.download_path(run_id),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="compliance_matrix.xlsx",
        )

    @app.get("/api/runs/{run_id}/events")
    async def events(
        run_id: str,
        after_event_id: Annotated[int, Query(ge=0)] = 0,
        last_event_id: Annotated[int | None, Header(ge=0)] = None,
    ) -> StreamingResponse:
        """Replay after a browser reconnect header or explicit refresh cursor."""
        cursor = last_event_id if last_event_id is not None else after_event_id
        store.replay(run_id, cursor)  # Validate before sending SSE response headers.
        return StreamingResponse(
            stream_events(store, run_id, cursor, settings.heartbeat_seconds),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
