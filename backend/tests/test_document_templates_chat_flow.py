from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from docx import Document
from PIL import Image

from app.main import app
from app.services.vision_service import VisionExtractionResult
from app.storage.runtime import blob_storage
from tests.auth_helpers import build_authed_client


@dataclass
class _NoopResponse:
    content: bytes = b"%PDF-1.7"

    def raise_for_status(self) -> None:
        return


def _make_docx_template() -> bytes:
    doc = Document()
    doc.add_paragraph("VIN: {{vin}}")
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (16, 16), color=(255, 255, 255))
    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def test_chat_flow_low_confidence_vin_requires_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DOCUMENTS_CONVERTER_ENABLED", "false")
    monkeypatch.setenv("VSELLM_API_KEY", "test-key")

    def _extract_vin(_self: Any, _image_bytes: bytes) -> VisionExtractionResult:
        return VisionExtractionResult(
            value="1HGCM82633A004352",
            confidence=0.7,
            valid=True,
            needs_confirmation=True,
        )

    monkeypatch.setattr("app.services.vision_service.VisionService.extract_vin", _extract_vin)
    monkeypatch.setattr("app.services.chat_service.ChatService._extract_template_fields_with_llm", lambda *args, **kwargs: {})

    client = build_authed_client(tmp_path, monkeypatch, "flow@example.com", "Flow")

    template_key = "templates/chat-flow-template.docx"
    blob_storage.put_bytes(template_key, _make_docx_template())

    created = client.post(
        "/api/document-templates",
        json={
            "name": "Гарантия Geely",
            "description": "Шаблон",
            "provider": "google_drive",
            "file_id": template_key,
            "fields": [{"key": "vin", "label": "VIN", "type": "vin", "required": True}],
            "output_settings": {"format": "docx", "filename": "warranty"},
        },
    )
    assert created.status_code == 201

    chat = client.post("/api/chats", json={"title": "Template chat"})
    assert chat.status_code == 201
    chat_id = chat.json()["id"]

    upload = client.post(
        f"/api/session/{chat_id}/files",
        files=[("files", ("vin.jpg", _make_jpeg_bytes(), "image/jpeg"))],
    )
    assert upload.status_code == 201
    image_file_id = upload.json()["files"][0]["file_id"]

    start = client.post(
        "/api/chat/stream",
        json={"session_id": chat_id, "message": "Заполни шаблон Гарантия Geely"},
    )
    assert start.status_code == 200
    assert "Укажите значение для поля 'vin'" in start.text

    recognize = client.post(
        "/api/chat/stream",
        json={"session_id": chat_id, "message": "Смотри фото", "file_ids": [image_file_id]},
    )
    assert recognize.status_code == 200
    assert "Распознано '1HGCM82633A004352'. Верно?" in recognize.text

    confirm = client.post(
        "/api/chat/stream",
        json={"session_id": chat_id, "message": "да"},
    )
    assert confirm.status_code == 200
    assert "Шаблон заполнен." in confirm.text
    assert "[[ATTACHMENT:" in confirm.text

    app.dependency_overrides.clear()
