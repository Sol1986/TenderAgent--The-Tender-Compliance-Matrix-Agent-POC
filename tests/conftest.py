"""Deterministic fixtures run the real graph without external model calls."""

import os
from threading import Lock
from typing import Any, get_args

import pandas as pd
import pytest

from app.main import (
    ChunkFindings,
    DecisionSupportReport,
    FinalRequirementItem,
    Requirement,
    RequirementCategory,
    TenderAnalysis,
)


def pytest_configure() -> None:
    """Keep deterministic tests offline even when the local .env enables tracing."""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


def analysis_fixture() -> TenderAnalysis:
    """Supply all real categories with one evidence-backed test requirement."""
    categories = [
        RequirementCategory(category=name, status="NOT_FOUND")
        for name in get_args(RequirementCategory.model_fields["category"].annotation)
    ]
    categories[0] = RequirementCategory(
        category="submission",
        status="FOUND",
        requirements=[
            FinalRequirementItem(
                requirement="Submit the signed offer.",
                status="FOUND",
                requirement_type="MANDATORY",
                source_sections=["Submission"],
                evidence=["Submit the signed offer."],
            )
        ],
    )
    return TenderAnalysis(categories=categories)


class FakeModel:
    """Capture actual node invocations and return the requested structured type."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.lock = Lock()
        self.report_error = False

    def with_structured_output(self, schema: type) -> Any:
        """Mimic the minimal provider interface used by the existing agent."""
        model = self

        class Runnable:
            def invoke(self, prompt: str) -> Any:
                """Record each call under lock so concurrency assertions are sound."""
                with model.lock:
                    model.calls.append((schema.__name__, prompt))
                if schema is ChunkFindings:
                    if "IRRELEVANT" in prompt:
                        return ChunkFindings()
                    return ChunkFindings(
                        requirements=[
                            Requirement(
                                category="submission",
                                requirement="Submit the signed offer.",
                                status="FOUND",
                                source_section="Submission",
                                evidence="Submit the signed offer.",
                            )
                        ]
                    )
                if schema is TenderAnalysis:
                    return analysis_fixture()
                if model.report_error:
                    raise RuntimeError("DO_NOT_EXPOSE_SECRET_PROVIDER_DETAIL")
                return DecisionSupportReport(
                    executive_summary="A test tender requiring human review."
                )

        return Runnable()


class FakeTable:
    """Exercise actual DataFrame serialization without invoking a PDF parser."""

    def __init__(self) -> None:
        self.frame = pd.DataFrame(
            {"Item": ["Signature"], "Requirement": ["Submit signed offer"]}
        )

    def export_to_dataframe(self, doc: Any) -> pd.DataFrame:
        """Return source cell values for the structured table path."""
        return self.frame

    def export_to_markdown(self, doc: Any) -> str:
        """Use matching Markdown as a conservative coverage test fixture."""
        return self.frame.to_markdown(index=False)


class FakeDocument:
    """A minimal Docling document with both original text and structured tables."""

    def __init__(self, markdown: str | None = None, tables: list | None = None) -> None:
        self.tables = [FakeTable()] if tables is None else tables
        self.markdown = markdown or (
            "## Submission\nSubmit the signed offer before closing. Preserve this important source evidence.\n"
            "## UNIT PRICE TABLE\nPrototype section prose is filtered too.\n"
            + self.tables[0].export_to_markdown(self)
        )

    def export_to_markdown(self) -> str:
        """Return a stable document export for repeatable splitter assertions."""
        return self.markdown


@pytest.fixture
def fake_model() -> FakeModel:
    """Create a fresh model adapter per run/test."""
    return FakeModel()


@pytest.fixture
def document() -> FakeDocument:
    """Create a sample with both text and covered table input."""
    return FakeDocument()


@pytest.fixture
def outputs() -> dict[str, Any]:
    """A valid completed graph result for API transport tests."""
    return {
        "final_analysis": analysis_fixture(),
        "decision_report": DecisionSupportReport(
            executive_summary="Human review required."
        ),
    }
