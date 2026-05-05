from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.db.models.common import IntegrationProvider
from app.integrations.file_storage import FileStorageItem, FileStorageProvider
from app.integrations.google_drive_storage import GoogleDriveIntegration
from app.integrations.onedrive_storage import OneDriveIntegration
from app.integrations.yandex_disk_storage import YandexDiskIntegration
from sqlalchemy.orm import Session


class FileStorageProviderNotSupportedError(ValueError):
    pass


@dataclass
class StorageProviderInfo:
    provider: str
    supports_search: bool
    supports_move: bool
    supports_share: bool


class FileStorageService:
    def __init__(self, session: Session, *, user_id: str) -> None:
        self._session = session
        self._user_id = user_id
        self._registry: dict[str, Callable[[], FileStorageProvider]] = {
            IntegrationProvider.GOOGLE_DRIVE.value: lambda: GoogleDriveIntegration(session, user_id=user_id),
            IntegrationProvider.YANDEX_DISK.value: lambda: YandexDiskIntegration(session, user_id=user_id),
            IntegrationProvider.ONEDRIVE.value: lambda: OneDriveIntegration(session, user_id=user_id),
        }

    def list_providers(self) -> list[StorageProviderInfo]:
        return [
            StorageProviderInfo(
                provider=provider,
                supports_search=True,
                supports_move=True,
                supports_share=True,
            )
            for provider in sorted(self._registry.keys())
        ]

    def list(self, *, provider: str, path: str) -> list[FileStorageItem]:
        return self._get_provider(provider).list(path=path)

    def search(self, *, provider: str, query: str, path: str | None = None) -> list[FileStorageItem]:
        return self._get_provider(provider).search(query=query, path=path)

    def read(self, *, provider: str, item_id: str) -> bytes:
        return self._get_provider(provider).read(item_id=item_id)

    def write(self, *, provider: str, path: str, content: bytes, overwrite: bool = True) -> FileStorageItem:
        return self._get_provider(provider).write(path=path, content=content, overwrite=overwrite)

    def get_metadata(self, *, provider: str, item_id: str) -> FileStorageItem:
        return self._get_provider(provider).get_metadata(item_id=item_id)

    def delete(self, *, provider: str, item_id: str, confirmed: bool) -> None:
        self._get_provider(provider).delete(item_id=item_id, confirmed=confirmed)

    def move(self, *, provider: str, item_id: str, new_parent_id: str | None, new_name: str | None = None) -> FileStorageItem:
        return self._get_provider(provider).move(item_id=item_id, new_parent_id=new_parent_id, new_name=new_name)

    def share(self, *, provider: str, item_id: str, role: str = "reader") -> str:
        return self._get_provider(provider).share(item_id=item_id, role=role)

    def get_link(self, *, provider: str, item_id: str) -> str:
        return self._get_provider(provider).get_link(item_id=item_id)

    def _get_provider(self, provider: str) -> FileStorageProvider:
        build = self._registry.get(provider)
        if build is None:
            raise FileStorageProviderNotSupportedError(f"Неподдерживаемый provider: {provider}")
        return build()
