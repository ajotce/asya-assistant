from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import quote

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


class OneDriveIntegration(FileStorageProvider):
    provider_name = IntegrationProvider.ONEDRIVE.value
    _api_base = "https://graph.microsoft.com/v1.0"

    def __init__(self, session: Session, *, user_id: str, transport: httpx.BaseTransport | None = None) -> None:
        self._secrets = EncryptedSecretService(
            session,
            SecretCryptoService(get_settings().master_encryption_key),
        )
        self._token = self._secrets.get_secret(
            user_id=user_id,
            name=f"integration:{IntegrationProvider.ONEDRIVE.value}:access_token",
        )
        self._client = httpx.Client(
            base_url=self._api_base,
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            headers={"Authorization": f"Bearer {self._token}"},
            transport=transport,
        )

    def list(self, *, path: str) -> list[FileStorageItem]:
        target = self._children_path(path)
        response = self._request("GET", target)
        items = response.json().get("value", [])
        return [self._to_item(item) for item in items]

    def search(self, *, query: str, path: str | None = None) -> list[FileStorageItem]:
        base = path or ""
        items = self.list(path=base)
        needle = query.strip().lower()
        if not needle:
            return items
        return [item for item in items if needle in item.name.lower()]

    def get_metadata(self, *, item_id: str) -> FileStorageItem:
        response = self._request("GET", self._item_path(item_id))
        return self._to_item(response.json())

    def read(self, *, item_id: str) -> bytes:
        response = self._request("GET", f"{self._item_path(item_id)}:/content")
        return response.content

    def write(self, *, path: str, content: bytes, overwrite: bool = True) -> FileStorageFile:
        conflict_behavior = "replace" if overwrite else "fail"
        url = f"/me/drive/root:/{self._normalize_path(path)}:/content?@microsoft.graph.conflictBehavior={conflict_behavior}"
        self._request("PUT", url, content=content, headers={"Content-Type": "application/octet-stream"})
        item = self.get_metadata(item_id=path)
        if isinstance(item, FileStorageFolder):
            raise FileStorageError("Ожидался файл, но получена папка.")
        return item

    def create_folder(self, *, path: str) -> FileStorageFolder:
        normalized = self._normalize_path(path)
        parent = str(PurePosixPath(normalized).parent)
        parent_url = "/me/drive/root/children" if parent in {".", "/"} else f"/me/drive/root:/{parent}:/children"
        folder_name = PurePosixPath(normalized).name
        body = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename",
        }
        self._request("POST", parent_url, json=body)
        item = self.get_metadata(item_id=path)
        if isinstance(item, FileStorageFile):
            raise FileStorageError("Ожидалась папка, но получен файл.")
        return item

    def delete(self, *, item_id: str, confirmed: bool) -> None:
        if not confirmed:
            raise FileStorageConfirmationRequiredError("Удаление требует явного подтверждения action policy.")
        self._request("DELETE", self._item_path(item_id))

    def move(self, *, item_id: str, new_parent_id: str | None, new_name: str | None = None) -> FileStorageItem:
        body: dict[str, object] = {}
        if new_name:
            body["name"] = new_name
        if new_parent_id:
            body["parentReference"] = {"path": f"/drive/root:/{new_parent_id.lstrip('/')}"}
        response = self._request("PATCH", self._item_path(item_id), json=body)
        return self._to_item(response.json())

    def get_link(self, *, item_id: str) -> str:
        response = self._request("GET", self._item_path(item_id))
        web_url = str(response.json().get("webUrl", "")).strip()
        if not web_url:
            raise FileStorageError("Ссылка на файл недоступна.")
        return web_url

    def share(self, *, item_id: str, role: str = "reader") -> str:
        response = self._request(
            "POST",
            f"{self._item_path(item_id)}/createLink",
            json={"type": "view", "scope": "organization"},
        )
        link = str(response.json().get("link", {}).get("webUrl", "")).strip()
        if not link:
            raise FileStorageError("Не удалось создать ссылку доступа.")
        return link

    def _children_path(self, path: str) -> str:
        normalized = self._normalize_path(path)
        if not normalized:
            return "/me/drive/root/children"
        return f"/me/drive/root:/{normalized}:/children"

    def _item_path(self, path: str) -> str:
        normalized = self._normalize_path(path)
        return f"/me/drive/root:/{normalized}"

    @staticmethod
    def _normalize_path(path: str) -> str:
        raw = path.strip().lstrip("/")
        return quote(raw, safe="/")

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        self._raise_for_status(response)
        return response

    @staticmethod
    def _to_item(raw: dict) -> FileStorageItem:
        modified_raw = raw.get("lastModifiedDateTime")
        modified = None
        if isinstance(modified_raw, str) and modified_raw:
            modified = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))
        parent = raw.get("parentReference", {}).get("path", "")
        parent_prefix = "/drive/root:"
        parent_path = str(parent).removeprefix(parent_prefix).strip("/")
        name = str(raw.get("name", ""))
        path = f"{parent_path}/{name}".strip("/")
        is_folder = raw.get("folder") is not None
        if is_folder:
            return FileStorageFolder(
                id=str(raw.get("id", path or name)),
                name=name,
                path=path,
                modified_at=modified,
                provider=IntegrationProvider.ONEDRIVE.value,
            )
        return FileStorageFile(
            id=str(raw.get("id", path or name)),
            name=name,
            path=path,
            size_bytes=int(raw["size"]) if raw.get("size") is not None else 0,
            modified_at=modified,
            provider=IntegrationProvider.ONEDRIVE.value,
            mime_type=raw.get("file", {}).get("mimeType"),
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise FileStorageAuthError("Ошибка авторизации OneDrive.")
        raise FileStorageError(f"OneDrive API error: {response.status_code}")
