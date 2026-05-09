from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.services.docx_to_pdf_converter import DocxToPdfConverter


@dataclass
class _FakeResponse:
    content: bytes

    def raise_for_status(self) -> None:
        return


def test_convert_to_pdf_uses_http_converter(monkeypatch) -> None:
    called: dict[str, Any] = {}

    def _post(url: str, *args: Any, **kwargs: Any) -> _FakeResponse:
        called["url"] = url
        called["files"] = kwargs.get("files")
        return _FakeResponse(content=b"%PDF-1.7")

    monkeypatch.setattr("app.services.docx_to_pdf_converter.httpx.post", _post)

    settings = Settings(
        DOCUMENTS_CONVERTER_ENABLED=True,
        DOCUMENTS_CONVERTER_URL="http://libreoffice:8080",
    )
    service = DocxToPdfConverter(settings)

    pdf = service.convert_to_pdf(b"docx-content")

    assert pdf.startswith(b"%PDF")
    assert called["url"] == "http://libreoffice:8080/convert"
    assert called["files"]["file"][0] == "document.docx"
