from __future__ import annotations

import base64
from io import BytesIO

from docx import Document

from tests.auth_helpers import build_authed_client


def _build_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_documents_fill_docx(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("DOC_CONVERTER_ENABLED", "false")
    client = build_authed_client(tmp_path, monkeypatch, "docs-fill@example.com")

    template = _build_docx_bytes("Hello {{name}}")
    response = client.post(
        "/api/documents/fill",
        files={
            "template": ("template.docx", template, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        },
        data={"values_json": '{"name":"Anton"}', "output": "docx", "filename_base": "test"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["output"] == "docx"
    assert payload["files"][0]["filename"] == "test.docx"
    assert base64.b64decode(payload["files"][0]["content_base64"])


def test_documents_fill_pdf_without_converter(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("DOC_CONVERTER_ENABLED", "false")
    client = build_authed_client(tmp_path, monkeypatch, "docs-pdf@example.com")

    template = _build_docx_bytes("Hello {{name}}")
    response = client.post(
        "/api/documents/fill",
        files={
            "template": ("template.docx", template, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        },
        data={"values_json": '{"name":"Anton"}', "output": "pdf", "filename_base": "test"},
    )

    assert response.status_code == 502
    assert "конвертац" in response.json()["detail"].lower()
