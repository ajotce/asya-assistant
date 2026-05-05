from __future__ import annotations

from io import BytesIO

from docx import Document

from app.services.document_fill_service import DocumentFillService


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_placeholder_replacement_and_preview_validation() -> None:
    service = DocumentFillService()
    template = _docx_bytes("Гарантия на {{car_model}} для {{client_name}}, VIN {{vin}}")
    fields = [
        {"key": "client_name", "label": "ФИО", "type": "text", "required": True},
        {"key": "car_model", "label": "Модель", "type": "text", "required": True},
        {"key": "vin", "label": "VIN", "type": "vin", "required": True},
    ]
    values = {"client_name": "Иванов Иван", "car_model": "Geely Monjaro", "vin": "XW8ZZZ1BZGG123456"}

    preview = service.preview(template_fields=fields, values=values, template_bytes=template)
    assert preview.ok is True

    artifact = service.fill(
        template_fields=fields,
        values=values,
        template_bytes=template,
        output_filename="warranty",
        user_id="user-1",
    )
    loaded = Document(artifact.path)
    text = "\n".join(paragraph.text for paragraph in loaded.paragraphs)
    assert "{{vin}}" not in text
    assert "XW8ZZZ1BZGG123456" in text


def test_missing_and_invalid_fields() -> None:
    service = DocumentFillService()
    template = _docx_bytes("Клиент {{client_name}}, email {{email}}, VIN {{vin}}")
    fields = [
        {"key": "client_name", "label": "ФИО", "type": "text", "required": True},
        {"key": "email", "label": "Email", "type": "email", "required": True},
        {"key": "vin", "label": "VIN", "type": "vin", "required": True},
    ]
    values = {"client_name": " ", "email": "bad-email", "vin": "BADVIN"}

    preview = service.preview(template_fields=fields, values=values, template_bytes=template)
    assert "client_name" in preview.missing_fields
    assert "email" in preview.invalid_fields
    assert "vin" in preview.invalid_fields
