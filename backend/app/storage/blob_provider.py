from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BlobStorageProvider(Protocol):
    def put_bytes(self, key: str, payload: bytes) -> str:
        ...

    def get_bytes(self, key: str) -> bytes:
        ...

    def delete(self, key: str) -> None:
        ...


class LocalBlobStorageProvider:
    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, payload: bytes) -> str:
        target = self._resolve_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return key

    def get_bytes(self, key: str) -> bytes:
        target = self._resolve_key(key)
        return target.read_bytes()

    def delete(self, key: str) -> None:
        target = self._resolve_key(key)
        target.unlink(missing_ok=True)

    def _resolve_key(self, key: str) -> Path:
        safe_key = key.lstrip("/").replace("..", "_")
        return self._root / safe_key
