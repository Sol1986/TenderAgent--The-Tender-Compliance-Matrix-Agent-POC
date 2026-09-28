"""Deterministic coverage for Phase B parallel package extraction."""

import os
import subprocess
import sys
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import pandas as pd

from backend.main import (
    ChunkFindings,
    Requirement,
    prepare_document,
    run_solicitation_package,
)
from backend.solicitation_package import discover_solicitation_documents


class FakeTable:
    """Provide a structured table large enough to exercise row batching."""

    def export_to_dataframe(self, doc: Any) -> pd.DataFrame:
        """Return stable source values without invoking Docling."""
        return pd.DataFrame(
            {
                "Item": ["Signature", "Insurance", "Clearance"],
                "Requirement": ["Signed", "$5M", "Before award"],
            }
        )


class FakeParsedDocument:
    """Supply the minimal parsed-document surface used by preparation."""

    def __init__(self, filename: str, include_table: bool = True) -> None:
        self.filename = filename
        self.tables = [FakeTable()] if include_table else []

    def export_to_markdown(self) -> str:
        """Return one source-specific heading chunk."""
        return f"## Submission\n{self.filename}: the bidder must submit a signed offer."


class FakeModel:
    """Return one evidence-backed finding for every worker invocation."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.lock = Lock()

    def with_structured_output(self, schema: type) -> Any:
        """Mimic the configured provider while keeping tests offline."""
        model = self

        class Runnable:
            def invoke(self, prompt: str) -> ChunkFindings:
                with model.lock:
                    model.prompts.append(prompt)
                if schema is not ChunkFindings:
                    raise AssertionError(f"Unexpected schema invocation: {schema}")
                return ChunkFindings(
                    requirements=[
                        Requirement(
                            category="submission",
                            requirement="Submit the signed offer.",
                            status="FOUND",
                            source_section="Submission",
                            evidence="The bidder must submit a signed offer.",
                        )
                    ]
                )

        return Runnable()


def write_pdf_stub(path: Path) -> None:
    """Create a discovery-only PDF placeholder."""
    path.write_bytes(b"%PDF-1.7\n%%EOF")


def test_import_is_free_of_parsing_and_provider_configuration() -> None:
    """Importing the active agent must not parse files or require credentials."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; os.environ.pop('OPENAI_API_KEY', None); from backend import main; "
                "assert main.extractor is None"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LANGSMITH_TRACING": "false"},
    )
    assert result.returncode == 0, result.stderr


def test_prepare_document_preserves_all_text_and_batches_tables(
    tmp_path: Path,
) -> None:
    """Do not drop short clauses or named tables; bound tables by row count."""
    path = tmp_path / "pricing_schedule.pdf"
    write_pdf_stub(path)
    input_document = discover_solicitation_documents(tmp_path)[0]

    prepared = prepare_document(
        input_document,
        parser=lambda _: FakeParsedDocument(path.name),
        table_batch_max_rows=2,
    )

    assert len(prepared.chunks) == 1
    assert len(prepared.tables) == 2
    assert prepared.chunks[0].metadata["document_id"] == (
        input_document.document.document_id
    )
    assert [table["row_count"] for table in prepared.tables] == [2, 1]
    assert all(table["document_name"] == path.name for table in prepared.tables)


def test_package_processes_documents_in_parallel_and_collects_candidates(
    tmp_path: Path,
) -> None:
    """Every PDF completes independently and contributes grounded candidates."""
    write_pdf_stub(tmp_path / "main_solicitation.pdf")
    write_pdf_stub(tmp_path / "annex_a.pdf")
    barrier = Barrier(2)

    def parser(path: Path) -> FakeParsedDocument:
        barrier.wait(timeout=2)
        return FakeParsedDocument(path.name)

    model = FakeModel()
    result = run_solicitation_package(
        tmp_path,
        model,
        parser=parser,
        max_document_workers=2,
        graph_max_concurrency=2,
        table_batch_max_rows=2,
    )

    assert [document.processing_status for document in result.documents] == [
        "COMPLETE",
        "COMPLETE",
    ]
    assert [item.text_chunks for item in result.document_results] == [1, 1]
    assert [item.table_batches for item in result.document_results] == [2, 2]
    assert len(result.candidate_requirements) == 6
    assert [item.candidate_id for item in result.candidate_requirements] == [
        f"CAND-{index:04d}" for index in range(1, 7)
    ]
    assert {item.document_name for item in result.candidate_requirements} == {
        "annex_a.pdf",
        "main_solicitation.pdf",
    }
    assert any("annex_a.pdf" in prompt for prompt in model.prompts)
    assert any("main_solicitation.pdf" in prompt for prompt in model.prompts)


def test_one_document_failure_does_not_drop_successful_results(tmp_path: Path) -> None:
    """Record a failed PDF and continue extracting candidates from its peer."""
    write_pdf_stub(tmp_path / "good.pdf")
    write_pdf_stub(tmp_path / "bad.pdf")

    def parser(path: Path) -> FakeParsedDocument:
        if path.name == "bad.pdf":
            raise ValueError("sensitive parser detail")
        return FakeParsedDocument(path.name, include_table=False)

    result = run_solicitation_package(
        tmp_path,
        FakeModel(),
        parser=parser,
        max_document_workers=2,
    )

    by_name = {document.filename: document for document in result.documents}
    assert by_name["bad.pdf"].processing_status == "FAILED"
    assert by_name["bad.pdf"].processing_error == (
        "Document processing failed (ValueError)."
    )
    assert "sensitive parser detail" not in by_name["bad.pdf"].processing_error
    assert by_name["good.pdf"].processing_status == "COMPLETE"
    assert [item.document_name for item in result.candidate_requirements] == [
        "good.pdf"
    ]
