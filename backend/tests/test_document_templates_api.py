from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from docx import Document

from app.api.deps_auth import get_db_session
from app.main import app
from app.services.file_storage_service import FileStorageService
from tests.auth_helpers import override_db_session, setup_test_db


def _register_and_login(client: TestClient, email: str, name: str) -> None:
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "display_name": name, "password": "strong-pass-123"},
        ).status_code
        == 200
    )
    assert client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"}).status_code == 200


def _payload(name: str = "Гарантия Geely") -> dict:
    return {
        "name": name,
        "description": "Талон гарантии",
        "provider": "google_drive",
        "file_id": "doc-template-1",
        "fields": [
            {"key": "client_name", "label": "ФИО", "type": "text", "required": True},
            {"key": "vin", "label": "VIN", "type": "vin", "required": True},
        ],
        "output_settings": {"format": "docx", "filename": "warranty"},
    }


def _docx_template_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph("Талон для {{client_name}}")
    doc.add_paragraph("VIN: {{vin}}")
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_document_templates_crud_and_user_isolation(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "doc-a@example.com", "A")
    _register_and_login(client_b, "doc-b@example.com", "B")

    created = client_a.post("/api/document-templates", json=_payload())
    assert created.status_code == 201
    template_id = created.json()["id"]

    list_a = client_a.get("/api/document-templates")
    list_b = client_b.get("/api/document-templates")
    assert list_a.status_code == 200
    assert list_b.status_code == 200
    assert len(list_a.json()) == 1
    assert len(list_b.json()) == 0

    forbidden_update = client_b.patch(
        f"/api/document-templates/{template_id}",
        json=_payload(name="Чужой шаблон"),
    )
    assert forbidden_update.status_code == 404

    updated = client_a.patch(
        f"/api/document-templates/{template_id}",
        json=_payload(name="Гарантия Geely обновленная"),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Гарантия Geely обновленная"

    forbidden_delete = client_b.delete(f"/api/document-templates/{template_id}")
    assert forbidden_delete.status_code == 404

    deleted = client_a.delete(f"/api/document-templates/{template_id}")
    assert deleted.status_code == 204
    assert client_a.get("/api/document-templates").json() == []

    app.dependency_overrides.clear()


def test_document_template_fill_preview_and_download(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    _register_and_login(client, "doc-fill@example.com", "F")

    created = client.post("/api/document-templates", json=_payload())
    assert created.status_code == 201
    template_id = created.json()["id"]

    def _fake_read(self: FileStorageService, *, provider: str, item_id: str) -> bytes:
        return _docx_template_bytes()

    monkeypatch.setattr(FileStorageService, "read", _fake_read)

    preview = client.post(
        f"/api/document-templates/{template_id}/fill",
        json={"values": {"client_name": "Иванов Иван"}, "preview_only": True},
    )
    assert preview.status_code == 200
    assert preview.json()["ready"] is False
    assert "vin" in preview.json()["missing_fields"]

    invalid_vin = client.post(
        f"/api/document-templates/{template_id}/fill",
        json={"values": {"client_name": "Иванов Иван", "vin": "123"}, "preview_only": False},
    )
    assert invalid_vin.status_code == 422

    download = client.post(
        f"/api/document-templates/{template_id}/fill",
        json={"values": {"client_name": "Иванов Иван", "vin": "XW8ZZZ1BZGG123456"}, "preview_only": False},
    )
    assert download.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in download.headers["content-type"]
    assert len(download.content) > 0

    app.dependency_overrides.clear()
