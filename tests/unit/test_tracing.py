"""Verify the package pipeline exposes explicit LangSmith stage boundaries."""

from langsmith.run_helpers import is_traceable_function

from app.main import (
    build_compliance_report,
    discover_package_documents,
    export_compliance_matrix_workbook,
    invoke_document_parser,
    prepare_document,
    process_document,
    reconcile_package,
    resolve_package,
    run_compliance_solicitation_package,
    run_solicitation_package,
    save_compliance_report,
    trace_package_inputs,
)


def test_full_package_stages_are_traceable() -> None:
    """Keep every material non-LLM stage visible in the parent trace."""
    traced_functions = (
        run_compliance_solicitation_package,
        run_solicitation_package,
        discover_package_documents,
        process_document,
        prepare_document,
        invoke_document_parser,
        reconcile_package,
        resolve_package,
        build_compliance_report,
        save_compliance_report,
        export_compliance_matrix_workbook,
    )

    assert all(is_traceable_function(function) for function in traced_functions)


def test_parent_trace_inputs_exclude_model_parser_and_absolute_paths() -> None:
    """Tracing metadata must not serialize provider clients or private paths."""
    traced = trace_package_inputs(
        {
            "package_path": r"C:\private\customer\tender_package",
            "output_path": r"C:\private\customer\outputs\report.json",
            "spreadsheet_output_path": r"C:\private\customer\outputs\matrix.xlsx",
            "model": object(),
            "parser": object(),
            "max_document_workers": 2,
            "graph_max_concurrency": 3,
            "table_batch_max_rows": 25,
        }
    )

    assert traced == {
        "package_folder": "tender_package",
        "json_output": "report.json",
        "spreadsheet_output": "matrix.xlsx",
        "max_document_workers": 2,
        "graph_max_concurrency": 3,
        "table_batch_max_rows": 25,
    }
