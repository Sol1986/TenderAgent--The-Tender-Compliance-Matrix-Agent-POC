"""FastAPI composition for a local single-process tender demonstration."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Annotated
from urllib.parse import unquote

from fastapi import FastAPI, Header, Query, Request
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
        allow_headers=[
            "Content-Type",
            "Idempotency-Key",
            "Last-Event-ID",
            "X-Tender-Filename",
        ],
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
            size = settings.sample_pdf().stat().st_size
        except OSError:
            size = None
        return [
            {
                "id": "sample-tender",
                "display_name": "tender.pdf",
                "size_bytes": size,
                "available": size is not None and size > 0,
            }
        ]

    @app.get("/api/tenders/{input_id}/pdf")
    async def view_tender(input_id: str) -> FileResponse:
        """View the same allowlisted PDF that will be analyzed."""
        return FileResponse(
            store.input_pdf(input_id),
            media_type="application/pdf",
            filename="tender.pdf",
            content_disposition_type="inline",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.post("/api/tenders", status_code=201)
    async def upload_tender(
        request: Request,
        filename: Annotated[str, Header(alias="X-Tender-Filename", max_length=1024)],
    ) -> dict[str, str]:
        """Bound upload bytes before validating a readable, unencrypted PDF."""
        name = unquote(filename).replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(char for char in name if char.isprintable())[:180]
        if (
            not name.casefold().endswith(".pdf")
            or request.headers.get("content-type", "").split(";")[0]
            != "application/pdf"
        ):
            raise DemoError("INVALID_PDF", "Upload a PDF file only.", 422)
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > settings.max_upload_bytes:
                raise DemoError(
                    "UPLOAD_TOO_LARGE", "This PDF exceeds the upload size limit.", 413
                )
            content.extend(chunk)

        def validate_and_save() -> str:
            """Keep PDF parsing and disk writes off the event-loop thread."""
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError

            if not content.startswith(b"%PDF-"):
                raise DemoError("INVALID_PDF", "This file is not a readable PDF.", 422)
            try:
                reader = PdfReader(BytesIO(content))
                if reader.is_encrypted:
                    raise DemoError(
                        "ENCRYPTED_PDF",
                        "Upload a PDF without password protection.",
                        422,
                    )
                pages = len(reader.pages)
            except (PdfReadError, ValueError, TypeError, KeyError, OSError) as exc:
                raise DemoError(
                    "INVALID_PDF", "This file is not a readable PDF.", 422
                ) from exc
            if not 1 <= pages <= settings.max_upload_pages:
                raise DemoError(
                    "PDF_PAGE_LIMIT",
                    "This PDF exceeds the page limit or has no pages.",
                    422,
                )
            return store.add_upload(bytes(content), name)

        input_id = await asyncio.to_thread(validate_and_save)
        return {
            "input_id": input_id,
            "display_name": name,
            "view_url": f"/api/tenders/{input_id}/pdf",
        }

    @app.post("/api/runs", status_code=202)
    async def start(
        body: StartRequest,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
        ],
    ) -> dict[str, str]:
        """Validate the selection and return before agent work finishes."""
        # Validate only new starts; an idempotent retry can restore a completed
        # run even if the source file has since become unavailable.
        with store.lock:
            store.prune()
            if idempotency_key not in store.keys:
                store.input_pdf(body.input_id)
            snapshot = executor.start(idempotency_key, body.input_id)
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
