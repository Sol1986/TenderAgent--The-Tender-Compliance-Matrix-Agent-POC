"""Verify uploads, preview identity, validation, and real-run input isolation."""

from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from dashboard.api import runner
from dashboard.api.app import create_app
from dashboard.api.config import Settings
from tests.integration.test_demo_api import await_terminal


def pdf_bytes(pages: int = 1, password: str | None = None) -> bytes:
    """Make valid local PDFs so signature-only impostors cannot pass validation."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=400)
    if password:
        writer.encrypt(password)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_uploaded_pdf_is_previewed_and_isolated_from_sample(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Exercise the live runner's selected path, not just the start response."""
    package = tmp_path / "sample"
    package.mkdir()
    sample = pdf_bytes()
    uploaded = pdf_bytes(2)
    (package / "tender.PDF").write_bytes(sample)
    (package / "unrelated.pdf").write_bytes(pdf_bytes(3))
    settings = Settings(sample_path=package, output_root=tmp_path / "runs")
    seen: list[bytes] = []
    monkeypatch.setattr("langchain_openai.ChatOpenAI", lambda **_kwargs: object())
    monkeypatch.setattr(runner, "matrix_requirements", lambda _report: ["requirement"])

    def pipeline(**kwargs: Any) -> object:
        """Capture the exact single PDF that would reach the package graph."""
        sources = list(kwargs["package_path"].glob("*.pdf"))
        assert len(sources) == 1
        seen.append(sources[0].read_bytes())
        kwargs["spreadsheet_output_path"].write_bytes(b"xlsx")
        return object()

    monkeypatch.setattr(runner, "run_compliance_solicitation_package", pipeline)
    with TestClient(create_app(settings)) as client:
        preview = client.get("/api/tenders/sample-tender/pdf")
        assert preview.content == sample
        assert "inline" in preview.headers["content-disposition"]
        assert client.get("/api/demo-inputs").json()[0]["size_bytes"] == len(sample)
        response = client.post(
            "/api/tenders",
            content=uploaded,
            headers={
                "Content-Type": "application/pdf",
                "X-Tender-Filename": "..%2Fmy-tender.pdf",
            },
        )
        assert response.status_code == 201
        selection = response.json()
        assert selection["display_name"] == "my-tender.pdf"
        assert client.get(selection["view_url"]).content == uploaded
        start = client.post(
            "/api/runs",
            json={"input_id": selection["input_id"]},
            headers={"Idempotency-Key": "upload"},
        )
        result = await_terminal(client, start.json()["run_id"])
        assert result["status"] == "completed"
        assert result["input"]["display_name"] == "my-tender.pdf"
        assert client.get(result["output"]["excel_url"]).content == b"xlsx"
        retry = client.post(
            "/api/runs",
            json={"input_id": selection["input_id"]},
            headers={"Idempotency-Key": "upload"},
        )
        assert retry.json()["run_id"] == result["run_id"]
        conflict = client.post(
            "/api/runs",
            json={"input_id": "sample-tender"},
            headers={"Idempotency-Key": "upload"},
        )
        assert conflict.status_code == 409
        default = client.post(
            "/api/runs",
            json={"input_id": "sample-tender"},
            headers={"Idempotency-Key": "sample"},
        )
        assert await_terminal(client, default.json()["run_id"])["status"] == "completed"
        assert seen == [uploaded, sample]
        assert (package / "tender.PDF").read_bytes() == sample


@pytest.mark.parametrize(
    "content,name,code",
    [
        (b"not a pdf", "notes.pdf", "INVALID_PDF"),
        (b"%PDF-broken", "broken.pdf", "INVALID_PDF"),
        (pdf_bytes(), "notes.txt", "INVALID_PDF"),
        (pdf_bytes(password="secret"), "locked.pdf", "ENCRYPTED_PDF"),
        (pdf_bytes(2), "large.pdf", "PDF_PAGE_LIMIT"),
    ],
)
def test_invalid_uploads_never_create_runs(
    tmp_path: Path, content: bytes, name: str, code: str
) -> None:
    """Reject invalid documents before allocating a provider-backed run."""
    app = create_app(Settings(output_root=tmp_path, max_upload_pages=1))
    with TestClient(app) as client:
        response = client.post(
            "/api/tenders",
            content=content,
            headers={"Content-Type": "application/pdf", "X-Tender-Filename": name},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == code
        assert not app.state.store.records and not app.state.store.uploads


def test_upload_size_and_capacity_limits(tmp_path: Path) -> None:
    """Bound storage and return actionable errors without provider calls."""
    headers = {"Content-Type": "application/pdf", "X-Tender-Filename": "tender.pdf"}
    with TestClient(
        create_app(Settings(output_root=tmp_path, max_upload_bytes=10))
    ) as client:
        assert (
            client.post(
                "/api/tenders", content=pdf_bytes(), headers=headers
            ).status_code
            == 413
        )
    with TestClient(
        create_app(Settings(output_root=tmp_path, max_uploads=1))
    ) as client:
        assert (
            client.post(
                "/api/tenders", content=pdf_bytes(), headers=headers
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/tenders", content=pdf_bytes(), headers=headers
            ).status_code
            == 429
        )
