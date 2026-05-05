from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.file_storage import FileStorageFile, FileStorageFolder
from app.services.file_storage_service import FileStorageService
from tests.auth_helpers import setup_test_db


@dataclass
class _FakeProvider:
    provider_name: str

    def list(self, *, path: str):
        return [FileStorageFolder(id=f"{self.provider_name}-root", name="root", path=path, modified_at=None, provider=self.provider_name)]

    def search(self, *, query: str, path: str | None = None):
        return [FileStorageFile(id=f"{self.provider_name}-f", name=query, path=path or "", size_bytes=1, modified_at=None, provider=self.provider_name)]

    def get_metadata(self, *, item_id: str):
        return FileStorageFile(
            id=item_id,
            name="meta.txt",
            path=item_id,
            size_bytes=1,
            modified_at=datetime.now(timezone.utc),
            provider=self.provider_name,
        )

    def read(self, *, item_id: str) -> bytes:
        return item_id.encode("utf-8")

    def write(self, *, path: str, content: bytes, overwrite: bool = True):
        return FileStorageFile(id=path, name=path, path=path, size_bytes=len(content), modified_at=None, provider=self.provider_name)

    def create_folder(self, *, path: str):
        return FileStorageFolder(id=path, name=path, path=path, modified_at=None, provider=self.provider_name)

    def delete(self, *, item_id: str, confirmed: bool) -> None:
        return None

    def move(self, *, item_id: str, new_parent_id: str | None, new_name: str | None = None):
        return self.get_metadata(item_id=item_id)

    def get_link(self, *, item_id: str) -> str:
        return f"https://example.test/{item_id}"

    def share(self, *, item_id: str, role: str = "reader") -> str:
        return f"https://example.test/shared/{item_id}"


def test_registry_contains_google_yandex_onedrive(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    with Session(bind=engine) as session:
        service = FileStorageService(session, user_id="u1")
        service._registry = {
            "google_drive": lambda: _FakeProvider("google_drive"),
            "yandex_disk": lambda: _FakeProvider("yandex_disk"),
            "onedrive": lambda: _FakeProvider("onedrive"),
        }

        providers = service.list_providers()
        names = [item.provider for item in providers]
        assert names == ["google_drive", "onedrive", "yandex_disk"]


def test_service_is_user_scoped_by_instance(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    with Session(bind=engine) as session:
        a = FileStorageService(session, user_id="user-a")
        b = FileStorageService(session, user_id="user-b")
        a._registry = {"google_drive": lambda: _FakeProvider("google_drive")}
        b._registry = {"google_drive": lambda: _FakeProvider("google_drive")}

        file_a = a.write(provider="google_drive", path="a.txt", content=b"A")
        file_b = b.write(provider="google_drive", path="b.txt", content=b"B")
        assert file_a.path == "a.txt"
        assert file_b.path == "b.txt"
