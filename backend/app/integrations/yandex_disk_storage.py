from __future__ import annotations

from datetime import datetime
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


class YandexDiskIntegration(FileStorageProvider):
    provider_name = IntegrationProvider.YANDEX_DISK.value
    _api_base = "https://cloud-api.yandex.net/v1/disk"

    def __init__(self, session: Session, *, user_id: str, transport: httpx.BaseTransport | None = None) -> None:
        self._secrets = EncryptedSecretService(
            session,
            SecretCryptoService(get_settings().master_encryption_key),
        )
        self._token = self._secrets.get_secret(
            user_id=user_id,
            name=f"integration:{IntegrationProvider.YANDEX_DISK.value}:access_token",
        )
        self._client = httpx.Client(
            base_url=self._api_base,
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            headers={"Authorization": f"OAuth {self._token}"},
            transport=transport,
        )

    def list(self, *, path: str) -> list[FileStorageItem]:
        response = self._request("GET", "/resources", params={"path": path or "/"})
        embedded = response.json().get("_embedded", {})
        items = embedded.get("items", [])
        return [self._to_item(item) for item in items]

    def search(self, *, query: str, path: str | None = None) -> list[FileStorageItem]:
        list_path = path or "/"
        items = self.list(path=list_path)
        needle = query.strip().lower()
        if not needle:
            return items
        return [item for item in items if needle in item.name.lower()]

    def get_metadata(self, *, item_id: str) -> FileStorageItem:
        response = self._request("GET", "/resources", params={"path": item_id})
        return self._to_item(response.json())

    def read(self, *, item_id: str) -> bytes:
        response = self._request("GET", "/resources/download", params={"path": item_id})
        href = str(response.json().get("href", "")).strip()
        if not href:
            raise FileStorageError("Yandex.Disk не вернул ссылку на скачивание.")
        download_response = self._client.get(href)
        self._raise_for_status(download_response)
        return download_response.content

    def write(self, *, path: str, content: bytes, overwrite: bool = True) -> FileStorageFile:
        response = self._request(
            "GET",
            "/resources/upload",
            params={"path": path, "overwrite": str(overwrite).lower()},
        )
        href = str(response.json().get("href", "")).strip()
        if not href:
            raise FileStorageError("Yandex.Disk не вернул ссылку для upload.")
        upload_response = self._client.put(href, content=content)
        self._raise_for_status(upload_response)
        item = self.get_metadata(item_id=path)
        if isinstance(item, FileStorageFolder):
            raise FileStorageError("Ожидался файл, но получена папка.")
        return item

    def create_folder(self, *, path: str) -> FileStorageFolder:
        self._request("PUT", "/resources", params={"path": path})
        item = self.get_metadata(item_id=path)
        if isinstance(item, FileStorageFile):
            raise FileStorageError("Ожидалась папка, но получен файл.")
        return item

    def delete(self, *, item_id: str, confirmed: bool) -> None:
        if not confirmed:
            raise FileStorageConfirmationRequiredError("Удаление требует явного подтверждения action policy.")
        self._request("DELETE", "/resources", params={"path": item_id, "permanently": "false"})

    def move(self, *, item_id: str, new_parent_id: str | None, new_name: str | None = None) -> FileStorageItem:
        target = f"{new_parent_id.rstrip('/')}/{new_name or item_id.rsplit('/', maxsplit=1)[-1]}" if new_parent_id else (
            new_name or item_id
        )
        self._request("POST", "/resources/move", params={"from": item_id, "path": target, "overwrite": "false"})
        return self.get_metadata(item_id=target)

    def get_link(self, *, item_id: str) -> str:
        response = self._request("GET", "/resources", params={"path": item_id})
        public_url = str(response.json().get("public_url", "")).strip()
        if public_url:
            return public_url
        raise FileStorageError("Публичная ссылка не доступна для ресурса.")

    def share(self, *, item_id: str, role: str = "reader") -> str:
        response = self._request("PUT", "/resources/publish", params={"path": item_id})
        href = str(response.json().get("href", "")).strip()
        if href:
            return href
        return self.get_link(item_id=item_id)

    def _request(self, method: str, url: str, *, params: dict[str, str]) -> httpx.Response:
        response = self._client.request(method, url, params=params)
        self._raise_for_status(response)
        return response

    @staticmethod
    def _to_item(raw: dict) -> FileStorageItem:
        modified_raw = raw.get("modified")
        modified = None
        if isinstance(modified_raw, str) and modified_raw:
            modified = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))
        path = str(raw.get("path", ""))
        name = str(raw.get("name", path.rsplit("/", maxsplit=1)[-1]))
        is_folder = str(raw.get("type", "")).lower() == "dir"
        item_id = path or quote(name)
        if is_folder:
            return FileStorageFolder(
                id=item_id,
                name=name,
                path=path,
                modified_at=modified,
                provider=IntegrationProvider.YANDEX_DISK.value,
            )
        return FileStorageFile(
            id=item_id,
            name=name,
            path=path,
            size_bytes=int(raw["size"]) if raw.get("size") is not None else 0,
            modified_at=modified,
            provider=IntegrationProvider.YANDEX_DISK.value,
            mime_type=raw.get("mime_type"),
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise FileStorageAuthError("Ошибка авторизации Yandex.Disk.")
        raise FileStorageError(f"Yandex.Disk API error: {response.status_code}")
