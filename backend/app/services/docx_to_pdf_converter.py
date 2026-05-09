from __future__ import annotations

import httpx

from app.core.config import Settings


class DocxToPdfConverter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def convert_to_pdf(self, docx_bytes: bytes) -> bytes:
        if not self._settings.documents_converter_enabled:
            raise RuntimeError("DOCX->PDF converter is disabled")

        files = {
            "file": (
                "document.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        response = httpx.post(
            f"{self._settings.documents_converter_url.rstrip('/')}/convert",
            files=files,
            timeout=httpx.Timeout(timeout=self._settings.documents_converter_timeout_seconds, connect=5.0),
        )
        response.raise_for_status()
        return response.content
