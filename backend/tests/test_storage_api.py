from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps_auth import get_db_session
from app.main import app
from app.services.file_storage_service import FileStorageService
from tests.auth_helpers import override_db_session, setup_test_db


def _register_and_login(client: TestClient, email: str, name: str) -> None:
    assert client.post("/api/auth/register", json={"email": email, "display_name": name, "password": "strong-pass-123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"}).status_code == 200


def test_storage_files_api_is_user_scoped(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    original_list = FileStorageService.list

    def fake_list(self: FileStorageService, *, provider: str, path: str):
        from app.integrations.file_storage import FileStorageFolder

        return [FileStorageFolder(id=f"{self._user_id}-folder", name=self._user_id, path=path, modified_at=None, provider=provider)]

    monkeypatch.setattr(FileStorageService, "list", fake_list)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "a-storage@example.com", "A")
    _register_and_login(client_b, "b-storage@example.com", "B")

    resp_a = client_a.get("/api/storage/files", params={"provider": "google_drive", "path": ""})
    resp_b = client_b.get("/api/storage/files", params={"provider": "google_drive", "path": ""})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()[0]["name"] != resp_b.json()[0]["name"]

    monkeypatch.setattr(FileStorageService, "list", original_list)
    app.dependency_overrides.clear()


def test_storage_providers_endpoint_returns_supported_set(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "providers@example.com", "P")
    resp = client.get("/api/storage/providers")
    assert resp.status_code == 200
    providers = {item["provider"] for item in resp.json()}
    assert {"google_drive", "yandex_disk", "onedrive"}.issubset(providers)
    app.dependency_overrides.clear()
