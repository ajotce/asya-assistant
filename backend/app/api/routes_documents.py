from __future__ import annotations

import base64
import json
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps_auth import get_current_user
from app.core.config import get_settings
from app.db.models.user import User
from app.models.schemas import DocumentConvertResponse, DocumentFillResponse, DocumentFilePayload
from app.services.document_converter import DocumentConversionError, LibreOfficeHttpConverter
from app.services.document_fill_service import DocumentFillService

router = APIRouter(tags=["documents"])


_OUTPUT_FORMATS = {"docx", "pdf", "both"}


def _build_service() -> DocumentFillService:
    settings = get_settings()
    converter = None
    if settings.doc_converter_enabled:
        converter = LibreOfficeHttpConverter(
            base_url=settings.doc_converter_url,
            timeout_seconds=settings.doc_converter_timeout_seconds,
        )
    return DocumentFillService(converter=converter)


def _normalize_filename_base(name: str) -> str:
    base = name.strip()
    base = re.sub(r"\.[^.]+$", "", base)
    base = re.sub(r"[^a-zA-Zа-яА-Я0-9_-]+", "_", base)
    return base or "document"


def _encode_file(filename: str, content_type: str, content: bytes) -> DocumentFilePayload:
    return DocumentFilePayload(
        filename=filename,
        content_type=content_type,
        content_base64=base64.b64encode(content).decode("ascii"),
    )


@router.post("/documents/fill", response_model=DocumentFillResponse)
async def fill_document_template(
    template: UploadFile = File(...),
    values_json: str = Form(default="{}"),
    output: str = Form(default="docx"),
    filename_base: str = Form(default="document"),
    _current_user: User = Depends(get_current_user),
) -> DocumentFillResponse:
    output_norm = output.strip().lower()
    if output_norm not in _OUTPUT_FORMATS:
        raise HTTPException(status_code=400, detail="Параметр output должен быть docx, pdf или both.")

    if not template.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Шаблон должен быть DOCX-файлом.")

    try:
        values_raw = json.loads(values_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="values_json должен быть валидным JSON-объектом.") from exc

    if not isinstance(values_raw, dict):
        raise HTTPException(status_code=400, detail="values_json должен быть JSON-объектом.")

    values = {str(key): str(value) for key, value in values_raw.items()}
    safe_base = _normalize_filename_base(filename_base)

    service = _build_service()
    payload = await template.read()

    try:
        bundle = service.fill_template(
            template_bytes=payload,
            values=values,
            output_format=output_norm,  # type: ignore[arg-type]
            filename_base=safe_base,
        )
    except DocumentConversionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось заполнить шаблон: {exc}") from exc

    return DocumentFillResponse(
        output=output_norm,
        files=[_encode_file(item.filename, item.content_type, item.content) for item in bundle.files],
    )


@router.post("/documents/convert", response_model=DocumentConvertResponse)
async def convert_docx_to_pdf(
    file: UploadFile = File(...),
    filename_base: str = Form(default="document"),
    _current_user: User = Depends(get_current_user),
) -> DocumentConvertResponse:
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Для конвертации нужен DOCX-файл.")

    service = _build_service()
    payload = await file.read()

    try:
        converted = service.convert_existing_docx(payload, filename_base=_normalize_filename_base(filename_base))
    except DocumentConversionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return DocumentConvertResponse(file=_encode_file(converted.filename, converted.content_type, converted.content))
