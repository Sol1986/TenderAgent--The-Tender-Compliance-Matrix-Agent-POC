"""Page references must come from identifiable source evidence."""

from types import SimpleNamespace

from app.source_pages import assign_source_pages, locate_page


def test_page_locator_requires_a_unique_supported_match() -> None:
    pages = [
        "Bidders must provide a signed integrity declaration with the proposal.",
        "The equipment schedule lists quantities for the installation work.",
    ]
    assert (
        locate_page("Provide a signed integrity declaration with the proposal.", pages)
        == 1
    )
    assert locate_page("signed integrity declaration", pages) is None
    assert locate_page("must provide a signed", pages) == 1
    assert (
        locate_page(
            "Provide a signed integrity declaration with the proposal.",
            [pages[0], pages[0]],
        )
        is None
    )
    assert (
        locate_page("unrelated evidence not present in either source page", pages)
        is None
    )


def test_report_pages_use_table_provenance_and_pdf_text(tmp_path, monkeypatch) -> None:
    """A rerun fills Pg without asking the model to invent a page number."""
    pdf = tmp_path / "tender.pdf"
    pdf.write_bytes(b"placeholder")

    class Reader:
        def __init__(self, _path):
            self.pages = [
                SimpleNamespace(
                    extract_text=lambda: (
                        "Bidders must provide a signed integrity declaration with the proposal."
                    )
                ),
                SimpleNamespace(extract_text=lambda: "Unit price table."),
            ]

    monkeypatch.setattr("app.source_pages.PdfReader", Reader)
    document = SimpleNamespace(document_id="DOC-000000000001", filename="tender.pdf")
    prose = SimpleNamespace(
        document_id=document.document_id,
        section="2.1",
        page=None,
        text="Provide a signed integrity declaration with the proposal.",
    )
    table = SimpleNamespace(
        document_id=document.document_id,
        section="tender.pdf - Table 3, rows 1-13",
        page=None,
        text="Estimated quantity and total price.",
    )
    requirements = [
        SimpleNamespace(
            sources=SimpleNamespace(evidence=[prose]),
            requirement=SimpleNamespace(page=None),
        ),
        SimpleNamespace(
            sources=SimpleNamespace(evidence=[table]),
            requirement=SimpleNamespace(page=None),
        ),
    ]
    report = SimpleNamespace(documents_analyzed=[document], requirements=requirements)
    result = SimpleNamespace(document=document, table_pages={3: 2})

    assign_source_pages(report, [result], tmp_path)

    assert prose.page == 1
    assert table.page == 2
    assert [item.requirement.page for item in requirements] == [1, 2]
