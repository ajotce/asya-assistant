from __future__ import annotations

from dataclasses import dataclass

import httpx


class DocumentConversionError(RuntimeError):
    """Raised when DOCX->PDF conversion fails."""


@dataclass(slots=True)
class LibreOfficeHttpConverter:
    base_url: str
    timeout_seconds: int = 30

    def convert(self, docx_bytes: bytes) -> bytes:
        if not docx_bytes:
            raise DocumentConversionError("Пустой DOCX-файл нельзя конвертировать в PDF.")

        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/convert/docx-to-pdf",
                files={
                    "file": (
                        "document.docx",
                        docx_bytes,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise DocumentConversionError(
                "Сервис конвертации PDF временно недоступен. Попробуйте позже."
            ) from exc

        if response.status_code >= 400:
            detail = response.text.strip() or "Не удалось конвертировать DOCX в PDF."
            raise DocumentConversionError(f"Ошибка конвертации PDF: {detail}")

        if not response.content:
            raise DocumentConversionError("Сервис конвертации вернул пустой PDF.")

        return response.content
