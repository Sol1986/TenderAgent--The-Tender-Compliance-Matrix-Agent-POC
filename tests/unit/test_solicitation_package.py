"""Unit coverage for Phase A solicitation-package ingestion."""

from pathlib import Path

import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from solicitation_package import (
    PackageDiscoveryError,
    SolicitationDocument,
    attach_document_identity,
    classify_document_type,
    discover_solicitation_documents,
)


def write_pdf_stub(path: Path) -> None:
    """Create enough bytes for discovery tests, which do not parse PDF content."""
    path.write_bytes(b"%PDF-1.7\n%%EOF")


def test_discovery_filters_and_registers_visible_pdfs(tmp_path: Path) -> None:
    """Find case-insensitive PDFs while ignoring hidden and unrelated files."""
    write_pdf_stub(tmp_path / "main_solicitation.pdf")
    write_pdf_stub(tmp_path / "Annex_A.PDF")
    write_pdf_stub(tmp_path / ".hidden.pdf")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    documents = discover_solicitation_documents(tmp_path)

    assert [item.document.filename for item in documents] == [
        "Annex_A.PDF",
        "main_solicitation.pdf",
    ]
    assert [item.document.document_type for item in documents] == [
        "ANNEX",
        "MAIN_SOLICITATION",
    ]
    assert all(item.document.processing_status == "PENDING" for item in documents)
    assert all(item.source_path.is_absolute() for item in documents)


def test_document_ids_are_stable_across_discovery_runs(tmp_path: Path) -> None:
    """The same original filename must produce the same internal identity."""
    write_pdf_stub(tmp_path / "Amendment_001.pdf")
    first = discover_solicitation_documents(tmp_path)[0]
    second = discover_solicitation_documents(tmp_path)[0]

    assert first.document.document_id == second.document.document_id
    assert first.document.document_id.startswith("DOC-")


@pytest.mark.parametrize("make_file", [False, True])
def test_discovery_rejects_invalid_or_empty_folder(
    tmp_path: Path, make_file: bool
) -> None:
    """Fail clearly when a package cannot supply any PDFs."""
    target = tmp_path / "package"
    if make_file:
        target.write_text("not a directory", encoding="utf-8")
    else:
        target.mkdir()

    with pytest.raises(PackageDiscoveryError):
        discover_solicitation_documents(target)


def test_classification_uses_early_content_and_defaults_safely() -> None:
    """Content can provide a strong signal while uncertainty remains OTHER."""
    assert (
        classify_document_type("document.pdf", "Request for Proposal 123")
        == "MAIN_SOLICITATION"
    )
    assert classify_document_type("document.pdf", "General project material") == "OTHER"
    assert (
        classify_document_type(
            "tender.pdf",
            "Invitation to Tender. Terms set out herein and in attached annexes.",
        )
        == "MAIN_SOLICITATION"
    )
    assert (
        classify_document_type(
            "document.pdf",
            "General project material incorporates Annex E by reference.",
        )
        == "OTHER"
    )


def test_chunk_identity_comes_from_registry() -> None:
    """Trusted registry metadata replaces conflicting model-facing metadata."""
    source = SolicitationDocument(
        document_id="DOC-0123456789AB",
        filename="annex.pdf",
        document_type="ANNEX",
    )
    original = Document(
        page_content="The bidder must submit the form.",
        metadata={"section": "Submission", "document_id": "untrusted"},
    )

    result = attach_document_identity([original], source)

    assert result[0].metadata == {
        "section": "Submission",
        "document_id": "DOC-0123456789AB",
        "document_name": "annex.pdf",
    }
    assert original.metadata["document_id"] == "untrusted"


def test_processing_error_requires_failed_status() -> None:
    """A registry record cannot expose an error while claiming success."""
    with pytest.raises(ValidationError, match="FAILED"):
        SolicitationDocument(
            document_id="DOC-0123456789AB",
            filename="main.pdf",
            processing_status="COMPLETE",
            processing_error="parser failed",
        )
