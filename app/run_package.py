"""Command-line entry point for package-level compliance analysis."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.main import (
    DEFAULT_COMPLIANCE_MATRIX_PATH,
    DEFAULT_COMPLIANCE_REPORT_PATH,
    DEFAULT_TENDER_PACKAGE_PATH,
    run_compliance_solicitation_package,
)


def build_parser() -> argparse.ArgumentParser:
    """Describe the one-command package analysis interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyze every top-level PDF in one solicitation package and write "
            "one authoritative JSON report plus one Excel compliance matrix."
        )
    )
    parser.add_argument(
        "--package",
        type=Path,
        default=DEFAULT_TENDER_PACKAGE_PATH,
        help=f"PDF folder (default: {DEFAULT_TENDER_PACKAGE_PATH})",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_COMPLIANCE_REPORT_PATH,
        help=f"JSON destination (default: {DEFAULT_COMPLIANCE_REPORT_PATH})",
    )
    parser.add_argument(
        "--xlsx-output",
        type=Path,
        default=DEFAULT_COMPLIANCE_MATRIX_PATH,
        help=f"Excel destination (default: {DEFAULT_COMPLIANCE_MATRIX_PATH})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model name; defaults to OPENAI_MODEL from the environment.",
    )
    parser.add_argument(
        "--document-workers",
        type=int,
        default=4,
        help="Maximum PDFs processed concurrently (default: 4).",
    )
    parser.add_argument(
        "--graph-concurrency",
        type=int,
        default=4,
        help="Maximum extraction workers per document (default: 4).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Load local configuration, run the package, and print artifact locations."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    parser = build_parser()
    args = parser.parse_args(argv)
    model_name = args.model or os.getenv("OPENAI_MODEL")
    if not model_name:
        parser.error("Set OPENAI_MODEL in .env or pass --model.")

    model = ChatOpenAI(model=model_name)
    report = run_compliance_solicitation_package(
        model=model,
        package_path=args.package,
        output_path=args.json_output,
        spreadsheet_output_path=args.xlsx_output,
        max_document_workers=args.document_workers,
        graph_max_concurrency=args.graph_concurrency,
    )
    print(f"Documents processed: {report.summary.documents_processed}")
    print(f"Documents failed: {report.summary.documents_failed}")
    print(f"Final requirements: {report.summary.total_requirements}")
    print(f"JSON: {args.json_output.resolve()}")
    print(f"Excel: {args.xlsx_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
