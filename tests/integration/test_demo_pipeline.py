"""Opt-in real parser/provider checks, separate from the fast offline suite."""

import os
from pathlib import Path
from typing import Any

import pytest

from main import run_single_document_analysis, validate_analysis


@pytest.mark.real_parser
@pytest.mark.skipif(
    os.getenv("DEMO_TEST_REAL_PARSER") != "1",
    reason="Set DEMO_TEST_REAL_PARSER=1 to run Docling on the supplied PDF.",
)
def test_real_sample_parser_to_graph(fake_model: Any) -> None:
    """Exercise real PDF preparation and the real graph with deterministic models."""
    events: list[tuple[str, dict[str, Any]]] = []

    def observe(kind: str, **fields: Any) -> None:
        """Collect runtime boundaries to verify the map/reduce join."""
        events.append((kind, fields))

    result = run_single_document_analysis(Path("tender.PDF"), fake_model, observe)
    prepared = next(fields for kind, fields in events if kind == "inputs.prepared")
    assert prepared["data"]["text_chunks"] > 0
    assert prepared["data"]["tables"] > 0
    assert prepared["data"]["total_chunks"] == (
        prepared["data"]["text_chunks"] + prepared["data"]["tables"]
    )
    reduction = next(
        index
        for index, (kind, fields) in enumerate(events)
        if kind == "stage.started" and fields["stage"] == "reduce_findings"
    )
    assert (
        sum(kind == "worker.completed" for kind, _ in events[:reduction])
        == prepared["data"]["total_chunks"]
    )
    assert len(validate_analysis(result["final_analysis"]).categories) == 15
    assert result["decision_report"].executive_summary
    assert sum(name == "TenderAnalysis" for name, _ in fake_model.calls) == 1
    assert sum(name == "DecisionSupportReport" for name, _ in fake_model.calls) == 1


@pytest.mark.live_provider
@pytest.mark.skipif(
    os.getenv("DEMO_TEST_LIVE_PROVIDER") != "1",
    reason="Explicit opt-in required: this invokes the configured paid provider.",
)
def test_live_sample_outputs() -> None:
    """Run an explicitly requested live-provider rehearsal without synthetic output."""
    from langchain_openai import ChatOpenAI

    from demo_api.config import Settings

    settings = Settings.from_env()
    model = ChatOpenAI(
        model=settings.model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    result = run_single_document_analysis(settings.sample_path, model)
    assert len(validate_analysis(result["final_analysis"]).categories) == 15
    assert result["decision_report"].executive_summary
