"""Regression coverage for the active import-safe agent and demo adapter."""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from langchain_core.documents import Document

from main import (
    InputDocument,
    Requirement,
    SolicitationDocument,
    analyze_chunk,
    analyze_table,
    configure_model,
    generate_report,
    prepare_document,
    reduce_findings,
    run_single_document_analysis,
    run_tender_analysis,
    stable_document_id,
    validate_analysis,
)


def input_document(filename: str = "unused.pdf") -> InputDocument:
    """Build one source record without requiring the file to exist."""
    return InputDocument(
        document=SolicitationDocument(
            document_id=stable_document_id(filename),
            filename=filename,
        ),
        source_path=Path(filename).resolve(),
    )


def table_input(table_data: str = "Minimum two certified personnel.") -> dict[str, Any]:
    """Supply the complete trusted metadata required by a table worker."""
    return {
        "table_number": 1,
        "table_id": "DOC-000000000001-T0001-B0001",
        "table_data": table_data,
        "document_id": "DOC-000000000001",
        "document_name": "unused.pdf",
        "row_start": 1,
        "row_end": 1,
    }


def test_import_does_not_parse_or_construct_provider() -> None:
    """Importing without credentials must not write artifacts or configure a model."""
    path = Path("tender.md")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; os.environ.pop('OPENAI_API_KEY', None); import main; "
                "assert main.extractor is None; assert main.reducer_llm is None"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("worker", ["chunk", "table"])
def test_workers_receive_recall_policy(fake_model: Any, worker: str) -> None:
    """Check the real prompts for the deliberate recall-first extraction policy."""
    evidence = "Award subject to clearance; minimum two certified personnel."
    configure_model(fake_model)
    if worker == "chunk":
        analyze_chunk(
            {
                "chunk": Document(
                    page_content=evidence,
                    metadata={
                        "section": "Award",
                        "document_id": "DOC-000000000001",
                        "document_name": "unused.pdf",
                    },
                )
            }
        )
    else:
        analyze_table(table_input(evidence))

    schema, prompt = fake_model.calls[-1]
    assert schema == "ChunkFindings"
    assert evidence in prompt
    assert "extract it as a candidate rather than omit it" in prompt
    assert "NOT keyword matching" in prompt
    assert "verbatim supporting evidence" in prompt
    assert 'prefix requirement with "Review needed:"' in prompt


def test_reconciliation_and_report_keep_review_boundary(
    fake_model: Any, outputs: dict[str, Any]
) -> None:
    """Ensure ambiguity and amendment instructions reach downstream model calls."""
    finding = Requirement(
        category="submission",
        requirement="Review needed: conflicting submission deadlines.",
        status="FOUND",
        source_section="Addendum 2",
        evidence="Closing September 30; revised closing October 2.",
    )
    configure_model(fake_model)
    reduce_findings({"findings": [finding]})
    prompt = fake_model.calls[-1][1]
    assert finding.evidence in prompt and finding.source_section in prompt
    assert "Merge only true duplicates" in prompt
    assert "a later date alone" in prompt
    assert "Uncertainty alone never justifies omission" in prompt
    assert "Do not promote an uncertain candidate" in prompt

    generate_report({"final_analysis": outputs["final_analysis"]})
    report_prompt = fake_model.calls[-1][1]
    assert 'Items prefixed "Review needed:" are unresolved candidates' in report_prompt
    assert "You must NOT make the bid/no-bid decision" in report_prompt


def test_preparation_retains_short_sections_and_structured_tables(
    document: Any,
) -> None:
    """Current preparation keeps short obligations and all table coverage."""
    document.markdown = "# Title\n## Tiny\nSign.\n" + document.export_to_markdown()
    prepared = prepare_document(input_document(), parser=lambda _path: document)

    assert any("Sign." in chunk.page_content for chunk in prepared.chunks)
    assert any(
        chunk.metadata.get("section") == "UNIT PRICE TABLE" for chunk in prepared.chunks
    )
    assert len(prepared.tables) == 1
    assert "Submit signed offer" in prepared.tables[0]["table_data"]
    assert all(
        chunk.metadata["document_name"] == "unused.pdf" for chunk in prepared.chunks
    )


@pytest.mark.parametrize("text_count,table_count", [(2, 2), (2, 0), (0, 2)])
def test_graph_joins_all_workers_once(
    fake_model: Any, text_count: int, table_count: int
) -> None:
    """Run the real graph across text-only, table-only, and mixed inputs."""
    chunks = [
        Document(
            page_content="Submit signed offer",
            metadata={
                "chunk_id": f"chunk-{index}",
                "document_id": "DOC-000000000001",
                "document_name": "unused.pdf",
            },
        )
        for index in range(text_count)
    ]
    tables = [
        table_input("IRRELEVANT") | {"table_number": index + 1}
        for index in range(table_count)
    ]

    result = run_tender_analysis(chunks, tables, fake_model, max_concurrency=2)

    assert len(result["findings"]) == text_count
    assert [name for name, _ in fake_model.calls].count("TenderAnalysis") == 1
    assert [name for name, _ in fake_model.calls].count("DecisionSupportReport") == 1
    assert result["final_analysis"].categories[0].requirements[0].evidence


def test_run_pipeline_emits_preparation_workers_and_outputs(
    fake_model: Any, document: Any
) -> None:
    """Exercise the compatibility runner through the active main module."""
    events: list[tuple[str, dict[str, Any]]] = []

    def observe(kind: str, **fields: Any) -> None:
        events.append((kind, fields))

    result = run_single_document_analysis(
        Path("unused.pdf"), fake_model, observe, parser=lambda _path: document
    )

    prepared = next(data for kind, data in events if kind == "inputs.prepared")
    reduction_index = next(
        index
        for index, (kind, data) in enumerate(events)
        if kind == "stage.started" and data["stage"] == "reduce_findings"
    )
    assert result["decision_report"].executive_summary
    assert prepared["data"] == {
        "total_chunks": 3,
        "text_chunks": 2,
        "tables": 1,
    }
    assert sum(kind == "worker.completed" for kind, _ in events[:reduction_index]) == 3
    assert [data["stage"] for kind, data in events if kind == "stage.started"][:2] == [
        "parse_document",
        "prepare_inputs",
    ]


def test_analysis_invariants(outputs: dict[str, Any]) -> None:
    """Schema validation must not silently invent missing categories."""
    analysis = outputs["final_analysis"].model_copy(deep=True)
    analysis.categories.pop()
    with pytest.raises(ValueError, match="exactly once"):
        validate_analysis(analysis)
