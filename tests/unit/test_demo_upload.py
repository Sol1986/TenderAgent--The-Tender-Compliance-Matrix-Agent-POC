"""Offline checks for the upload demo's package and artifact boundaries."""

from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader

from backend import demo_upload


def test_upload_batch_runs_once_and_returns_isolated_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    """Two PDFs must become one package and one downloadable output pair."""
    first = tmp_path / "main.pdf"
    second = tmp_path / "annex.PDF"
    first.write_bytes(b"%PDF-1.7\nmain")
    second.write_bytes(b"%PDF-1.7\nannex")
    monkeypatch.setattr(demo_upload, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(demo_upload, "ChatOpenAI", lambda model: model)
    monkeypatch.setenv("OPENAI_MODEL", "demo-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_pipeline(**kwargs) -> SimpleNamespace:
        """Write deterministic artifacts in the paths supplied by the UI."""
        calls.append(kwargs)
        assert sorted(path.name for path in kwargs["package_path"].iterdir()) == [
            "annex.PDF",
            "main.pdf",
        ]
        kwargs["output_path"].write_text("{}", encoding="utf-8")
        kwargs["spreadsheet_output_path"].write_bytes(b"xlsx")
        return SimpleNamespace(
            summary=SimpleNamespace(
                documents_processed=2, documents_failed=0, total_requirements=0
            ),
            model_dump=lambda **_: {
                "requirements": [],
                "documents_analyzed": [
                    {"filename": "main.pdf", "processing_status": "COMPLETE"},
                    {"filename": "annex.PDF", "processing_status": "COMPLETE"},
                ],
                "unresolved_issues": [],
            },
        )

    monkeypatch.setattr(
        demo_upload, "run_compliance_solicitation_package", fake_pipeline
    )
    status, excel, json_report, pdf, data, overview, matrix, refs = (
        demo_upload.analyze_uploads([str(first), str(second)])
    )

    assert len(calls) == 1
    assert calls[0]["model"] == "demo-model"
    assert "2 PDF(s) processed, 0 reconciled requirements" in status
    assert Path(excel).read_bytes() == b"xlsx"
    assert Path(json_report).read_text(encoding="utf-8") == "{}"
    assert Path(excel).parent == Path(json_report).parent
    assert first.read_bytes() == b"%PDF-1.7\nmain"
    assert Path(pdf).parent == Path(excel).parent
    assert "No active requirements" in PdfReader(pdf).pages[0].extract_text()
    assert data["counts"]["total"] == 0
    assert "main.pdf" in overview and "Showing 0 of 0" in matrix and "annex.PDF" in refs
