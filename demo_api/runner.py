"""Bounded execution outside HTTP handlers; reconnecting never starts work."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import ValidationError

from main_copy import PreparationError, run_tender

from .config import Settings
from .models import ErrorInfo, RunSnapshot
from .store import RunStore

logger = logging.getLogger(__name__)
Pipeline = Callable[..., dict[str, Any]]


class RunExecutor:
    """Own a single process-local worker and injectable pipeline for testing."""

    def __init__(
        self, settings: Settings, store: RunStore, pipeline: Pipeline | None = None
    ) -> None:
        self.settings, self.store = settings, store
        self.pipeline = pipeline or self._live_pipeline
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tender-demo")

    def _live_pipeline(self, observe: Callable[..., None]) -> dict[str, Any]:
        """Construct the provider only inside an accepted run."""
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=self.settings.model,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=self.settings.llm_max_retries,
        )
        return run_tender(
            self.settings.sample_path,
            model,
            observe,
            max_concurrency=self.settings.graph_concurrency,
            max_workers=self.settings.max_workers,
            max_input_characters=self.settings.max_input_characters,
        )

    def start(self, key: str) -> RunSnapshot:
        """Reserve capacity atomically, then schedule once without waiting."""
        snapshot, created = self.store.create(key)
        if created:
            try:
                self.pool.submit(self._execute, snapshot.run_id)
            except RuntimeError:
                self.store.finish(
                    snapshot.run_id,
                    error=ErrorInfo(
                        code="SERVER_STOPPING",
                        message="The demo server is stopping. Try again after restart.",
                    ),
                )
        return self.store.snapshot(snapshot.run_id)

    def _execute(self, run_id: str) -> None:
        """Translate failures without leaking provider exceptions or raw inputs."""
        from openai import OpenAIError

        def observe(kind: str, **fields: Any) -> None:
            self.store.observe(run_id, kind, **fields)

        observe("run.started", summary="Tender run started.")
        try:
            output = self.pipeline(observe)
            self.store.finish(run_id, output=output)
        except Exception as exc:  # noqa: BLE001 -- centralized worker failure boundary
            stages = self.store.snapshot(run_id).stages
            active = next(
                (stage.id for stage in stages if stage.status == "running"), None
            )
            if isinstance(exc, PreparationError) or active in {
                "parse_document",
                "prepare_inputs",
            }:
                code, message = (
                    "DOCUMENT_PROCESSING_FAILED",
                    "The sample could not be fully prepared. Check the parser and sample document.",
                )
            elif isinstance(exc, OpenAIError):
                code, message = (
                    "PROVIDER_FAILED",
                    "The model provider could not complete the run. Check server-side model access and configuration.",
                )
            elif isinstance(exc, (ValidationError, ValueError)):
                code, message = (
                    "INVALID_ANALYSIS_RESPONSE",
                    "The agent did not return a valid structured response.",
                )
            else:
                code, message = (
                    "GRAPH_EXECUTION_FAILED",
                    "The agent could not finish this run. Check the server configuration.",
                )
            logger.error(
                "run=%s code=%s failure_type=%s", run_id, code, type(exc).__name__
            )
            self.store.finish(run_id, error=ErrorInfo(code=code, message=message))

    def close(self) -> None:
        """Wait for in-flight work; browser disconnect is not cancellation."""
        self.pool.shutdown(wait=True)
