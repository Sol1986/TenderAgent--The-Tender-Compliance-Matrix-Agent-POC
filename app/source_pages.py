"""Recover verifiable PDF page coordinates for reconciled source evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader
from pypdf.errors import PdfReadError

if TYPE_CHECKING:
    from app.main import ComplianceReport, DocumentExtractionResult


def tokens(value: str) -> list[str]:
    """Normalize OCR punctuation and line breaks without changing word order."""
    return re.findall(r"[a-z0-9]+", value.casefold())


def locate_page(evidence_text: str, page_texts: list[str]) -> int | None:
    """Return a page only when its text uniquely supports the excerpt."""
    words = tokens(evidence_text)
    if len(words) < 4:
        return None
    excerpt = " ".join(words)
    normalized_pages = [" ".join(tokens(text)) for text in page_texts]
    samples = (
        (excerpt, excerpt[:160], excerpt[:80]) if len(excerpt) >= 25 else (excerpt,)
    )
    for sample in samples:
        matches = [
            index + 1 for index, page in enumerate(normalized_pages) if sample in page
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None

    if len(words) < 12:
        return None
    triples = {tuple(words[index : index + 3]) for index in range(len(words) - 2)}
    scores = []
    for index, page_text in enumerate(page_texts, 1):
        page_words = tokens(page_text)
        page_triples = {
            tuple(page_words[position : position + 3])
            for position in range(len(page_words) - 2)
        }
        scores.append((len(triples & page_triples) / len(triples), index))
    scores.sort(reverse=True)
    best, second = scores[0][0], scores[1][0] if len(scores) > 1 else 0.0
    return scores[0][1] if best >= 0.65 and best - second >= 0.15 else None


def assign_source_pages(
    report: ComplianceReport,
    document_results: list[DocumentExtractionResult],
    package_path: str | Path,
) -> None:
    """Fill missing page fields from table provenance or unique PDF text matches."""
    table_pages = {
        result.document.document_id: result.table_pages for result in document_results
    }
    page_texts_by_document: dict[str, list[str]] = {}
    package = Path(package_path)
    for document in report.documents_analyzed:
        pdf_path = package / document.filename
        if not pdf_path.is_file():
            continue
        try:
            page_texts_by_document[document.document_id] = [
                page.extract_text() or "" for page in PdfReader(pdf_path).pages
            ]
        except (OSError, PdfReadError):
            continue

    for item in report.requirements:
        for evidence in item.sources.evidence:
            if evidence.page is not None:
                continue
            table_match = re.search(
                r"\bTable\s+(\d+)\b", evidence.section or "", re.IGNORECASE
            )
            if table_match:
                evidence.page = table_pages.get(evidence.document_id, {}).get(
                    int(table_match.group(1))
                )
            if evidence.page is None:
                pages = page_texts_by_document.get(evidence.document_id, [])
                if pages:
                    evidence.page = locate_page(evidence.text, pages)
        if item.requirement.page is None:
            item.requirement.page = next(
                (evidence.page for evidence in item.sources.evidence if evidence.page),
                None,
            )
