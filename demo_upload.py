"""Small local upload UI for the package-level compliance pipeline."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from compliance_review import (
    REVIEW_CSS,
    STAGES,
    build_review_data,
    export_review_pdf,
    label,
    render_matrix,
    render_overview,
    render_references,
)
from main import run_compliance_solicitation_package

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_ROOT = PROJECT_ROOT / "outputs" / "demo_runs"
logger = logging.getLogger(__name__)


def analyze_uploads(
    uploaded_files: list[str] | None,
) -> tuple[str, str, str, str | None, dict[str, Any], str, str, str]:
    """Analyze one uploaded PDF package and return its own download paths."""
    if not uploaded_files:
        raise gr.Error("Upload at least one PDF before starting the analysis.")

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    model_name = os.getenv("OPENAI_MODEL")
    if not model_name or not os.getenv("OPENAI_API_KEY"):
        raise gr.Error("Set OPENAI_MODEL and OPENAI_API_KEY in the project .env file.")

    run_directory = RUNS_ROOT / uuid4().hex
    package_directory = run_directory / "tender_package"
    package_directory.mkdir(parents=True)
    seen_names: set[str] = set()

    for uploaded_file in uploaded_files:
        source = Path(str(uploaded_file))
        name = source.name
        if not source.is_file() or source.suffix.casefold() != ".pdf":
            raise gr.Error("Every uploaded file must be a readable PDF.")
        if name.casefold() in seen_names:
            raise gr.Error(f"Upload each PDF filename only once: {name}")
        seen_names.add(name.casefold())
        with source.open("rb") as pdf:
            if pdf.read(5) != b"%PDF-":
                raise gr.Error(f"{name} does not appear to be a PDF.")
        shutil.copy2(source, package_directory / name)

    json_path = run_directory / "compliance_report.json"
    excel_path = run_directory / "compliance_matrix.xlsx"
    try:
        report = run_compliance_solicitation_package(
            model=ChatOpenAI(model=model_name),
            package_path=package_directory,
            output_path=json_path,
            spreadsheet_output_path=excel_path,
        )
    except Exception as exc:
        logger.exception("Compliance analysis failed for run %s", run_directory.name)
        raise gr.Error(
            "The analysis did not finish. Check the terminal for the error, then try again."
        ) from exc

    status = (
        f"Done: {report.summary.documents_processed} PDF(s) processed, "
        f"{report.summary.total_requirements} reconciled requirements."
    )
    if report.summary.documents_failed:
        status += f" {report.summary.documents_failed} PDF(s) failed processing; review the JSON report."
    review = build_review_data(report.model_dump(mode="json"))
    pdf_path: str | None = None
    try:
        pdf_path = str(
            export_review_pdf(review, run_directory / "compliance_review.pdf")
        )
    except Exception:
        logger.exception("PDF export failed for run %s", run_directory.name)
        status += " PDF export failed; Excel, JSON, and the on-screen review are available. Check the terminal for details."
    return (
        status,
        str(excel_path),
        str(json_path),
        pdf_path,
        review,
        render_overview(review),
        render_matrix(review),
        render_references(review),
    )


def clear_results() -> tuple[Any, ...]:
    """Remove stale downloads and review content before a new run starts."""
    return (
        "Analyzing the uploaded package. This can take several minutes.",
        None,
        None,
        None,
        None,
        "",
        "",
        "",
        "",
        "All",
        "All",
        "All",
        "All",
        False,
    )


def show_review(data: dict[str, Any] | None) -> dict[str, Any]:
    """Reveal the report only when this session has a completed result."""
    return gr.update(visible=data is not None)


def clear_filters() -> tuple[str, str, str, str, str, bool]:
    """Restore the complete matrix without rerunning the agent."""
    return "", "All", "All", "All", "All", False


def build_theme() -> gr.themes.Base:
    """Set the three requested demo colors in both browser color modes."""
    return gr.themes.Base().set(
        body_background_fill="#0D0F18",
        body_background_fill_dark="#0D0F18",
        background_fill_primary="#0D0F18",
        background_fill_primary_dark="#0D0F18",
        body_text_color="#F2F5FF",
        body_text_color_dark="#F2F5FF",
        block_background_fill="#111521",
        block_background_fill_dark="#111521",
        panel_background_fill="#111521",
        panel_background_fill_dark="#111521",
        input_background_fill="#111521",
        input_background_fill_dark="#111521",
        button_primary_background_fill="#79B2FF",
        button_primary_background_fill_dark="#79B2FF",
        button_primary_background_fill_hover="#79B2FF",
        button_primary_background_fill_hover_dark="#79B2FF",
        button_primary_border_color="#79B2FF",
        button_primary_border_color_dark="#79B2FF",
        button_primary_text_color="#0D0F18",
        button_primary_text_color_dark="#0D0F18",
    )


def build_demo() -> gr.Blocks:
    """Expose the existing package runner through a minimal browser form."""
    with gr.Blocks(title="Compliance Matrix Generator Agent") as demo:
        gr.Markdown(
            "# Compliance Matrix Generator Agent\nUpload one or more PDFs from the same solicitation package."
        )
        pdfs = gr.File(
            label="Solicitation PDFs", file_count="multiple", file_types=[".pdf"]
        )
        start = gr.Button("Generate compliance matrix", variant="primary")
        status = gr.Textbox(label="Status", interactive=False)
        excel = gr.File(label="Download Excel compliance matrix")
        json_report = gr.File(label="Download JSON report")
        pdf_report = gr.File(label="Download PDF review")
        review_state = gr.State(None)
        with gr.Column(visible=False) as review_panel:
            overview = gr.HTML()
            with gr.Row():
                search = gr.Textbox(
                    label="Search requirements",
                    placeholder="Requirement ID, wording, or reference",
                )
                stage = gr.Dropdown(
                    choices=[
                        ("All stages", "All"),
                        *[(v, k) for k, v in STAGES.items()],
                    ],
                    value="All",
                    label="Stage",
                )
            with gr.Row():
                category = gr.Dropdown(
                    choices=[
                        ("All categories", "All"),
                        *[
                            (label(c), c)
                            for c in (
                                "submission",
                                "required_documents",
                                "certifications",
                                "insurance",
                                "bonding_security",
                                "experience",
                                "personnel",
                                "technical",
                                "financial",
                                "formatting",
                                "legal_regulatory",
                                "language",
                                "security",
                                "site_meeting",
                                "signatures",
                            )
                        ],
                    ],
                    value="All",
                    label="Category",
                )
                requirement_type = gr.Dropdown(
                    choices=[
                        ("All types", "All"),
                        *[
                            (label(t), t)
                            for t in (
                                "MANDATORY",
                                "REQUIRED",
                                "CONDITIONAL",
                                "INFORMATIONAL",
                            )
                        ],
                    ],
                    value="All",
                    label="Requirement type",
                )
                severity = gr.Dropdown(
                    choices=[
                        ("All severities", "All"),
                        *[
                            (label(s), s)
                            for s in (
                                "DISQUALIFYING",
                                "MAJOR",
                                "MINOR",
                                "INFORMATIONAL",
                                "UNKNOWN",
                            )
                        ],
                    ],
                    value="All",
                    label="Severity",
                )
            with gr.Row():
                review_only = gr.Checkbox(label="Needs review only")
                reset = gr.Button("Clear filters")
            matrix = gr.HTML()
            references = gr.HTML()
        filters = [search, stage, category, requirement_type, severity, review_only]
        outputs = [
            status,
            excel,
            json_report,
            pdf_report,
            review_state,
            overview,
            matrix,
            references,
        ]
        start.click(fn=clear_results, outputs=[*outputs, *filters], queue=False).then(
            fn=analyze_uploads,
            inputs=pdfs,
            outputs=outputs,
            show_progress="full",
        )
        review_state.change(show_review, review_state, review_panel, queue=False)
        for component in filters:
            component.change(
                render_matrix, [review_state, *filters], matrix, queue=False
            )
        reset.click(clear_filters, outputs=filters, queue=False)
    return demo


if __name__ == "__main__":
    build_demo().queue(max_size=5, default_concurrency_limit=1).launch(
        server_name="127.0.0.1",
        inbrowser=True,
        max_file_size=os.getenv("DEMO_MAX_UPLOAD_SIZE", "50mb"),
        theme=build_theme(),
        css=REVIEW_CSS,
    )
