"""Foundational models and ingestion helpers for solicitation packages.

This module owns the package boundary: it discovers and registers PDFs and
preserves their identity on parsed chunks. The active agent in ``main.py`` owns
document parsing and parallel candidate extraction.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type DocumentType = Literal[
    "MAIN_SOLICITATION",
    "ANNEX",
    "APPENDIX",
    "AMENDMENT",
    "ADDENDUM",
    "TECHNICAL_SPECIFICATION",
    "PRICING",
    "FORM",
    "INSTRUCTIONS",
    "Q_AND_A",
    "SECURITY_DOCUMENT",
    "OTHER",
]

type ProcessingStatus = Literal[
    "PENDING",
    "PROCESSING",
    "COMPLETE",
    "FAILED",
]


class PackageDiscoveryError(ValueError):
    """Explain why a folder cannot become a solicitation package."""


class SolicitationDocument(BaseModel):
    """Public registry record for one source PDF in a solicitation package."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(pattern=r"^DOC-[A-F0-9]{12}$")
    filename: str
    document_type: DocumentType = "OTHER"
    title: str | None = None
    solicitation_number: str | None = None
    amendment_number: str | None = None
    issue_date: str | None = None
    processing_status: ProcessingStatus = "PENDING"
    processing_error: str | None = None

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        """Keep display metadata as a filename rather than a filesystem path."""
        cleaned = value.strip()
        if not cleaned or Path(cleaned).name != cleaned:
            raise ValueError("filename must contain only the original file name")
        if Path(cleaned).suffix.casefold() != ".pdf":
            raise ValueError("filename must identify a PDF")
        return cleaned

    @model_validator(mode="after")
    def validate_processing_error(self) -> SolicitationDocument:
        """Prevent stale errors from appearing on documents that did not fail."""
        if self.processing_error and self.processing_status != "FAILED":
            raise ValueError("processing_error requires FAILED processing status")
        return self


class InputDocument(BaseModel):
    """Internal ingestion record with public metadata and a local source path."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    document: SolicitationDocument
    source_path: Path = Field(exclude=True)

    @model_validator(mode="after")
    def validate_source(self) -> InputDocument:
        """Ensure the private source corresponds to the registered PDF name."""
        if self.source_path.name != self.document.filename:
            raise ValueError("source_path name must match the registered filename")
        return self


def stable_document_id(filename: str) -> str:
    """Create a repeatable package-local ID without exposing a filesystem path."""
    normalized = filename.strip().encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()[:12].upper()
    return f"DOC-{digest}"


def classify_document_type(filename: str, early_text: str = "") -> DocumentType:
    """Classify strong filename/content signals and use OTHER when uncertain.

    Phase B can add an LLM fallback after parsing. This deterministic first pass
    avoids inventing metadata when neither the name nor early content is clear.
    """
    name = re.sub(r"[^a-z0-9]+", " ", Path(filename).stem.casefold())
    filename_rules: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
        ("Q_AND_A", ("questions and answers", "question and answer", "q and a")),
        ("AMENDMENT", ("amendment",)),
        ("ADDENDUM", ("addendum",)),
        ("ANNEX", ("annex",)),
        ("APPENDIX", ("appendix",)),
        (
            "SECURITY_DOCUMENT",
            ("security requirements checklist", "security requirement"),
        ),
        ("TECHNICAL_SPECIFICATION", ("technical specification", "statement of work")),
        ("PRICING", ("pricing schedule", "price schedule", "basis of payment")),
        ("INSTRUCTIONS", ("standard instructions", "instructions to bidders")),
        ("FORM", ("submission form", "certification form", "bid form")),
        (
            "MAIN_SOLICITATION",
            ("main solicitation", "request for proposal", "invitation to tender"),
        ),
    )
    for document_type, signals in filename_rules:
        if any(signal in name for signal in signals):
            return document_type

    # Content signals are deliberately stricter. Solicitation bodies routinely
    # mention annexes and amendments without being those document types.
    front_text = early_text[:4000].casefold()
    normalized_front = re.sub(r"[^a-z0-9]+", " ", front_text)
    heading_region = normalized_front[:600]
    meaningful_lines = [
        re.sub(r"[^a-z0-9]+", " ", line.casefold()).strip()
        for line in early_text[:4000].splitlines()
        if line.strip() and not line.lstrip().startswith("<!--")
    ]
    first_heading = meaningful_lines[0] if meaningful_lines else ""
    if any(
        signal in normalized_front
        for signal in ("request for proposal", "invitation to tender")
    ):
        return "MAIN_SOLICITATION"
    if any(
        signal in heading_region
        for signal in ("questions and answers", "question and answer", "q and a")
    ):
        return "Q_AND_A"
    if first_heading.startswith("amendment "):
        return "AMENDMENT"
    if first_heading.startswith("addendum "):
        return "ADDENDUM"
    if re.match(r"^annex\s+[a-z0-9]+\b", first_heading):
        return "ANNEX"
    if re.match(r"^appendix\s+[a-z0-9]+\b", first_heading):
        return "APPENDIX"
    if "security requirements checklist" in heading_region:
        return "SECURITY_DOCUMENT"
    if any(
        signal in heading_region
        for signal in ("technical specification", "statement of work")
    ):
        return "TECHNICAL_SPECIFICATION"
    if any(
        signal in heading_region
        for signal in ("pricing schedule", "price schedule", "basis of payment")
    ):
        return "PRICING"
    if any(
        signal in heading_region
        for signal in ("standard instructions", "instructions to bidders")
    ):
        return "INSTRUCTIONS"
    return "OTHER"


def discover_solicitation_documents(package_path: str | Path) -> list[InputDocument]:
    """Register every visible top-level PDF in a local solicitation folder."""
    root = Path(package_path)
    if not root.exists():
        raise PackageDiscoveryError(
            f"Solicitation package folder does not exist: {root}"
        )
    if not root.is_dir():
        raise PackageDiscoveryError(
            f"Solicitation package path is not a folder: {root}"
        )

    try:
        pdf_paths = sorted(
            (
                path
                for path in root.iterdir()
                if path.is_file()
                and not path.name.startswith(".")
                and path.suffix.casefold() == ".pdf"
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    except OSError as exc:
        raise PackageDiscoveryError(
            f"Solicitation package folder could not be read: {root}"
        ) from exc

    if not pdf_paths:
        raise PackageDiscoveryError(
            f"No PDF documents were found in solicitation package folder: {root}"
        )

    return [
        InputDocument(
            document=SolicitationDocument(
                document_id=stable_document_id(path.name),
                filename=path.name,
                document_type=classify_document_type(path.name),
            ),
            source_path=path.resolve(),
        )
        for path in pdf_paths
    ]


def register_pdf(path: str | Path, early_text: str = "") -> InputDocument:
    """Register one known PDF for the existing single-document pipeline."""
    source_path = Path(path)
    if not source_path.is_file() or source_path.suffix.casefold() != ".pdf":
        raise PackageDiscoveryError(f"PDF document does not exist: {source_path}")
    return InputDocument(
        document=SolicitationDocument(
            document_id=stable_document_id(source_path.name),
            filename=source_path.name,
            document_type=classify_document_type(source_path.name, early_text),
        ),
        source_path=source_path.resolve(),
    )


def attach_document_identity(
    chunks: Sequence[Document], document: SolicitationDocument
) -> list[Document]:
    """Copy chunks with registry-controlled source identity in their metadata."""
    identified: list[Document] = []
    for chunk in chunks:
        metadata = {
            **chunk.metadata,
            "document_id": document.document_id,
            "document_name": document.filename,
        }
        identified.append(chunk.model_copy(update={"metadata": metadata}))
    return identified
