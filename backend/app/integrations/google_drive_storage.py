from __future__ import annotations

from datetime import datetime
import json

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.integrations.file_storage import (
    FileStorageAuthError,
    FileStorageConfirmationRequiredError,
    FileStorageError,
    FileStorageFile,
    FileStorageFolder,
    FileStorageItem,
    FileStorageProvider,
)
from app.services.encrypted_secret_service import EncryptedSecretService
from app.services.secret_crypto_service import SecretCryptoService


class GoogleDriveIntegration(FileStorageProvider):
    provider_name = IntegrationProvider.GOOGLE_DRIVE.value
    _api_base = "https://www.googleapis.com/drive/v3"
    _upload_base = "https://www.googleapis.com/upload/drive/v3"

    def __init__(self, session: Session, *, user_id: str, transport: httpx.BaseTransport | None = None) -> None:
        secrets = EncryptedSecretService(session, SecretCryptoService(get_settings().master_encryption_key))
        token = secrets.get_secret(user_id=user_id, name=f"integration:{IntegrationProvider.GOOGLE_DRIVE.value}:access_token")
        headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.Client(
            base_url=self._api_base,
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            headers=headers,
            transport=transport,
        )
        self._upload_client = httpx.Client(
            base_url=self._upload_base,
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            headers=headers,
            transport=transport,
        )

    def list(self, *, path: str) -> list[FileStorageItem]:
        parent = path.strip() or "root"
        q = f"'{parent}' in parents and trashed=false"
        response = self._request(
            "GET",
            "/files",
            params={"q": q, "fields": "files(id,name,mimeType,size,modifiedTime,parents,webViewLink)"},
        )
        return [self._to_item(item) for item in response.json().get("files", [])]

    def search(self, *, query: str, path: str | None = None) -> list[FileStorageItem]:
        escaped = query.replace("'", "\\'")
        query_filter = f"name contains '{escaped}' and trashed=false"
        if path:
            query_filter = f"'{path}' in parents and {query_filter}"
        response = self._request(
            "GET",
            "/files",
            params={"q": query_filter, "fields": "files(id,name,mimeType,size,modifiedTime,parents,webViewLink)"},
        )
        return [self._to_item(item) for item in response.json().get("files", [])]

    def get_metadata(self, *, item_id: str) -> FileStorageItem:
        response = self._request(
            "GET",
            f"/files/{item_id}",
            params={"fields": "id,name,mimeType,size,modifiedTime,parents,webViewLink"},
        )
        return self._to_item(response.json())

    def read(self, *, item_id: str) -> bytes:
        response = self._request("GET", f"/files/{item_id}", params={"alt": "media"})
        return response.content

    def write(self, *, path: str, content: bytes, overwrite: bool = True) -> FileStorageFile:
        name = path.rsplit("/", maxsplit=1)[-1]
        parent = path.rsplit("/", maxsplit=1)[0] if "/" in path else "root"
        body = {"name": name, "parents": [parent]}
        response = self._upload_request(
            "POST",
            "/files",
            params={"uploadType": "multipart", "fields": "id,name,mimeType,size,modifiedTime,parents,webViewLink"},
            files={
                "metadata": ("metadata", json.dumps(body), "application/json"),
                "file": (name, content, "application/octet-stream"),
            },
        )
        item = self._to_item(response.json())
        if isinstance(item, FileStorageFolder):
            raise FileStorageError("Ожидался файл, но получена папка.")
        return item

    def create_folder(self, *, path: str) -> FileStorageFolder:
        name = path.rsplit("/", maxsplit=1)[-1]
        parent = path.rsplit("/", maxsplit=1)[0] if "/" in path else "root"
        response = self._request(
            "POST",
            "/files",
            params={"fields": "id,name,mimeType,size,modifiedTime,parents,webViewLink"},
            json={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]},
        )
        item = self._to_item(response.json())
        if isinstance(item, FileStorageFile):
            raise FileStorageError("Ожидалась папка, но получен файл.")
        return item

    def delete(self, *, item_id: str, confirmed: bool) -> None:
        if not confirmed:
            raise FileStorageConfirmationRequiredError("Удаление требует явного подтверждения action policy.")
        self._request("DELETE", f"/files/{item_id}")

    def move(self, *, item_id: str, new_parent_id: str | None, new_name: str | None = None) -> FileStorageItem:
        params: dict[str, str] = {"fields": "id,name,mimeType,size,modifiedTime,parents,webViewLink"}
        if new_parent_id:
            old = self._request("GET", f"/files/{item_id}", params={"fields": "parents"}).json().get("parents", [])
            params["addParents"] = new_parent_id
            if old:
                params["removeParents"] = ",".join(old)
        body = {"name": new_name} if new_name else {}
        response = self._request("PATCH", f"/files/{item_id}", params=params, json=body)
        return self._to_item(response.json())

    def get_link(self, *, item_id: str) -> str:
        response = self._request("GET", f"/files/{item_id}", params={"fields": "webViewLink"})
        link = str(response.json().get("webViewLink", "")).strip()
        if not link:
            raise FileStorageError("Ссылка на файл недоступна.")
        return link

    def share(self, *, item_id: str, role: str = "reader") -> str:
        self._request("POST", f"/files/{item_id}/permissions", json={"type": "anyone", "role": role})
        return self.get_link(item_id=item_id)

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        self._raise_for_status(response)
        return response

    def _upload_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._upload_client.request(method, url, **kwargs)
        self._raise_for_status(response)
        return response

    @staticmethod
    def _to_item(raw: dict) -> FileStorageItem:
        modified_raw = raw.get("modifiedTime")
        modified = None
        if isinstance(modified_raw, str) and modified_raw:
            modified = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))
        mime_type = str(raw.get("mimeType", ""))
        is_folder = mime_type == "application/vnd.google-apps.folder"
        if is_folder:
            return FileStorageFolder(
                id=str(raw.get("id", "")),
                name=str(raw.get("name", "")),
                path=str(raw.get("id", "")),
                modified_at=modified,
                provider=IntegrationProvider.GOOGLE_DRIVE.value,
            )
        return FileStorageFile(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            path=str(raw.get("id", "")),
            size_bytes=int(raw["size"]) if raw.get("size") is not None else 0,
            modified_at=modified,
            provider=IntegrationProvider.GOOGLE_DRIVE.value,
            mime_type=mime_type or None,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise FileStorageAuthError("Ошибка авторизации Google Drive.")
        raise FileStorageError(f"Google Drive API error: {response.status_code}")
