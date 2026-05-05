from __future__ import annotations

import json

import httpx
from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider, UserStatus
from app.integrations.file_storage import FileStorageConfirmationRequiredError
from app.integrations.onedrive_storage import OneDriveIntegration
from app.integrations.yandex_disk_storage import YandexDiskIntegration
from app.repositories.user_repository import UserRepository
from app.services.integration_connection_service import IntegrationConnectionService, IntegrationConnectionUpsertPayload
from tests.auth_helpers import setup_test_db


def _create_user(session: Session, *, email: str):
    user = UserRepository(session).create(
        email=email,
        display_name=email,
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return user


def _store_access_token(session: Session, *, user_id: str, provider: IntegrationProvider, token: str) -> None:
    service = IntegrationConnectionService(session)
    service.upsert_connection_by_user_id(
        user_id=user_id,
        payload=IntegrationConnectionUpsertPayload(
            provider=provider,
            status=IntegrationConnectionStatus.CONNECTED,
            scopes=["files.readwrite"],
            access_token=token,
        ),
    )


def test_yandex_disk_mocked_flow_and_delete_policy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.url.path == "/v1/disk/resources" and request.method == "GET":
            if request.url.params.get("path") == "/":
                return httpx.Response(
                    status_code=200,
                    json={
                        "_embedded": {
                            "items": [
                                {"name": "docs", "path": "disk:/docs", "type": "dir", "modified": "2026-05-03T10:00:00+00:00"},
                            ]
                        }
                    },
                )
            if request.url.params.get("path") == "disk:/new-folder":
                return httpx.Response(
                    status_code=200,
                    json={"name": "new-folder", "path": "disk:/new-folder", "type": "dir", "modified": "2026-05-03T10:00:00+00:00"},
                )
            return httpx.Response(
                status_code=200,
                json={"name": "a.txt", "path": "disk:/a.txt", "type": "file", "size": 5, "modified": "2026-05-03T10:00:00+00:00"},
            )
        if request.url.path == "/v1/disk/resources/download":
            return httpx.Response(status_code=200, json={"href": "https://download.local/file"})
        if str(request.url) == "https://download.local/file":
            return httpx.Response(status_code=200, content=b"hello")
        if request.url.path == "/v1/disk/resources/upload":
            return httpx.Response(status_code=200, json={"href": "https://upload.local/file"})
        if str(request.url) == "https://upload.local/file":
            return httpx.Response(status_code=201)
        if request.url.path == "/v1/disk/resources" and request.method in {"PUT", "DELETE"}:
            return httpx.Response(status_code=204)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    with Session(bind=engine) as session:
        user = _create_user(session, email="yandex-storage@example.com")
        _store_access_token(session, user_id=user.id, provider=IntegrationProvider.YANDEX_DISK, token="token-y")
        integration = YandexDiskIntegration(session, user_id=user.id, transport=httpx.MockTransport(handler))

        listed = integration.list(path="/")
        assert len(listed) == 1
        assert listed[0].name == "docs"

        meta = integration.get_metadata(item_id="disk:/a.txt")
        assert meta.name == "a.txt"
        assert integration.read(item_id="disk:/a.txt") == b"hello"
        integration.write(path="disk:/a.txt", content=b"hello-updated")
        integration.create_folder(path="disk:/new-folder")

        try:
            integration.delete(item_id="disk:/a.txt", confirmed=False)
            raise AssertionError("Delete without confirm must fail")
        except FileStorageConfirmationRequiredError:
            pass

        integration.delete(item_id="disk:/a.txt", confirmed=True)
        assert any(method == "DELETE" for method, _ in calls)


def test_onedrive_mocked_flow_and_delete_policy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.url.path == "/v1.0/me/drive/root/children" and request.method == "GET":
            return httpx.Response(
                status_code=200,
                json={
                    "value": [
                        {
                            "id": "1",
                            "name": "docs",
                            "folder": {},
                            "size": 0,
                            "lastModifiedDateTime": "2026-05-03T10:00:00Z",
                            "parentReference": {"path": "/drive/root:"},
                        }
                    ]
                },
            )
        if request.url.path == "/v1.0/me/drive/root:/docs/a.txt" and request.method == "GET":
            return httpx.Response(
                status_code=200,
                json={
                    "id": "2",
                    "name": "a.txt",
                    "size": 5,
                    "lastModifiedDateTime": "2026-05-03T10:00:00Z",
                    "parentReference": {"path": "/drive/root:/docs"},
                },
            )
        if request.url.path == "/v1.0/me/drive/root:/docs/new-folder" and request.method == "GET":
            return httpx.Response(
                status_code=200,
                json={
                    "id": "3",
                    "name": "new-folder",
                    "folder": {},
                    "size": 0,
                    "lastModifiedDateTime": "2026-05-03T10:00:00Z",
                    "parentReference": {"path": "/drive/root:/docs"},
                },
            )
        if request.url.path == "/v1.0/me/drive/root:/docs/a.txt:/content" and request.method == "GET":
            return httpx.Response(status_code=200, content=b"hello")
        if request.url.path == "/v1.0/me/drive/root:/docs/a.txt:/content" and request.method == "PUT":
            return httpx.Response(status_code=201)
        if request.url.path == "/v1.0/me/drive/root:/docs:/children" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            assert body["name"] == "new-folder"
            return httpx.Response(status_code=201)
        if request.url.path == "/v1.0/me/drive/root:/docs/a.txt" and request.method == "DELETE":
            return httpx.Response(status_code=204)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    with Session(bind=engine) as session:
        user = _create_user(session, email="onedrive-storage@example.com")
        _store_access_token(session, user_id=user.id, provider=IntegrationProvider.ONEDRIVE, token="token-o")
        integration = OneDriveIntegration(session, user_id=user.id, transport=httpx.MockTransport(handler))

        listed = integration.list(path="")
        assert len(listed) == 1
        assert listed[0].name == "docs"

        meta = integration.get_metadata(item_id="docs/a.txt")
        assert meta.name == "a.txt"
        assert integration.read(item_id="docs/a.txt") == b"hello"
        integration.write(path="docs/a.txt", content=b"hello-updated")
        integration.create_folder(path="docs/new-folder")

        try:
            integration.delete(item_id="docs/a.txt", confirmed=False)
            raise AssertionError("Delete without confirm must fail")
        except FileStorageConfirmationRequiredError:
            pass

        integration.delete(item_id="docs/a.txt", confirmed=True)
        assert any(method == "DELETE" for method, _ in calls)
