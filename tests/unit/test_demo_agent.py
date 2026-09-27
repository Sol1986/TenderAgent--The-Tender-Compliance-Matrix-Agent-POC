"""Regression coverage for the notebook logic and minimal adapter changes."""

import ast
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from main_copy import (
    PreparationError,
    TenderAgent,
    prepare_document,
    run_tender,
    split_markdown,
    validate_analysis,
)


def test_import_does_not_parse_or_construct_provider() -> None:
    """Import without credentials must not load Docling or write tender artifacts."""
    path = Path("tender.md")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sys; os.environ.pop('OPENAI_API_KEY',None); import main_copy; "
                "assert 'docling.document_converter' not in sys.modules; "
                "assert not hasattr(main_copy,'llm')"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_original_prompt_text_is_preserved() -> None:
    """AST comparisons ensure the four existing prompt bodies were not rewritten."""

    def prompts(filename: str) -> dict[str, str]:
        tree = ast.parse(Path(filename).read_text(encoding="utf-8"))
        return {
            node.name: ast.dump(
                next(
                    n.value
                    for n in ast.walk(node)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "prompt" for t in n.targets
                    )
                )
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {"analyze_chunk", "analyze_table", "reduce_findings", "generate_report"}
        }

    assert prompts("main_copy.py") == prompts("main.py")


def test_heading_split_and_filters_are_unchanged(document: Any) -> None:
    """Compare with the literal original splitting/filtering algorithm."""
    markdown = "# Title\n## Tiny\nSign.\n" + document.export_to_markdown()
    baseline = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "title"), ("##", "section"), ("###", "subsection")],
        strip_headers=False,
    ).split_text(markdown)
    expected = [
        c
        for c in baseline
        if len(c.page_content.strip()) >= 50
        and c.metadata.get("section") != "UNIT PRICE TABLE"
    ]
    actual, excluded, short = split_markdown(markdown)
    assert [c.page_content for c in actual] == [c.page_content for c in expected]
    assert excluded and short == 1
    assert actual[0].metadata["section"] == "Submission"


def test_table_coverage_and_input_limits(document: Any) -> None:
    """Never allow a filtered large table to disappear from both pipelines."""
    prepared = prepare_document(document)
    assert len(prepared.tables) == 1 and prepared.filtered_table == 1
    assert "Submit signed offer" in prepared.tables[0]["table_data"]
    with pytest.raises(PreparationError, match="worker limit"):
        prepare_document(document, max_workers=1)
    with pytest.raises(PreparationError, match="input limit"):
        prepare_document(document, max_input_characters=1)
    document.tables = []
    with pytest.raises(PreparationError, match="coverage"):
        prepare_document(document)


@pytest.mark.parametrize("text_count,table_count", [(2, 2), (2, 0), (0, 2)])
def test_graph_joins_all_workers_once(
    fake_model: Any, text_count: int, table_count: int
) -> None:
    """Use the real LangGraph topology and provider substitutes, including empty findings."""
    events = []

    def observe(kind: str, **fields: Any) -> None:
        events.append((kind, fields))

    chunks = [
        Document(
            page_content="Submit signed offer", metadata={"chunk_id": f"chunk-{i}"}
        )
        for i in range(text_count)
    ]
    tables = [
        {"table_number": i, "table_data": "IRRELEVANT"} for i in range(table_count)
    ]
    result = (
        TenderAgent(fake_model)
        .build_graph(observe)
        .invoke(
            {"chunks": chunks, "tables": tables, "findings": []},
            config={"max_concurrency": 2},
        )
    )
    assert len(result["findings"]) == text_count
    assert [name for name, _ in fake_model.calls].count("TenderAnalysis") == 1
    assert [name for name, _ in fake_model.calls].count("DecisionSupportReport") == 1
    reduction = next(
        i
        for i, (kind, data) in enumerate(events)
        if kind == "stage.started" and data["stage"] == "reduce_findings"
    )
    assert (
        sum(kind == "worker.completed" for kind, _ in events[:reduction])
        == text_count + table_count
    )
    assert result["final_analysis"].categories[0].requirements[0].evidence


def test_run_pipeline_emits_real_preparation_and_outputs(
    fake_model: Any, document: Any
) -> None:
    """Run the entire callable path with a supplied document and fresh model state."""
    events = []

    def observe(kind: str, **fields: Any) -> None:
        events.append((kind, fields))

    result = run_tender(
        Path("unused.pdf"), fake_model, observe, parser=lambda _: document
    )
    assert result["decision_report"].executive_summary
    assert any(
        kind == "run.warning" and "surrounding prose" in data["summary"]
        for kind, data in events
    )
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
