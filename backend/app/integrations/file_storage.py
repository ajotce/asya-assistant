from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class FileStorageError(RuntimeError):
    pass


class FileStorageAuthError(FileStorageError):
    pass


class FileStorageConfirmationRequiredError(FileStorageError):
    pass


@dataclass
class FileStorageFile:
    id: str
    name: str
    path: str
    size_bytes: int
    modified_at: datetime | None
    mime_type: str | None = None
    provider: str | None = None


@dataclass
class FileStorageFolder:
    id: str
    name: str
    path: str
    modified_at: datetime | None
    provider: str | None = None


FileStorageItem = FileStorageFile | FileStorageFolder


class SupportsFileStorageFactory(Protocol):
    def __call__(self, *, user_id: str) -> "FileStorageProvider": ...


class FileStorageProvider(ABC):
    provider_name: str

    @abstractmethod
    def list(self, *, path: str) -> list[FileStorageItem]:
        raise NotImplementedError

    @abstractmethod
    def search(self, *, query: str, path: str | None = None) -> list[FileStorageItem]:
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, *, item_id: str) -> FileStorageItem:
        raise NotImplementedError

    @abstractmethod
    def read(self, *, item_id: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, *, path: str, content: bytes, overwrite: bool = True) -> FileStorageFile:
        raise NotImplementedError

    @abstractmethod
    def create_folder(self, *, path: str) -> FileStorageFolder:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, item_id: str, confirmed: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def move(self, *, item_id: str, new_parent_id: str | None, new_name: str | None = None) -> FileStorageItem:
        raise NotImplementedError

    @abstractmethod
    def get_link(self, *, item_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def share(self, *, item_id: str, role: str = "reader") -> str:
        raise NotImplementedError
