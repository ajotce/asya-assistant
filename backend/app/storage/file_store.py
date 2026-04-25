from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List


@dataclass
class StoredSessionFile:
    file_id: str
    session_id: str
    filename: str
    content_type: str
    size_bytes: int
    path: str


class SessionFileStore:
    def __init__(self, base_tmp_dir: str) -> None:
        self._root = Path(base_tmp_dir).resolve() / "session-files"
        self._lock = Lock()
        self._files_by_session: Dict[str, List[StoredSessionFile]] = {}
        self._reset_root_dir()

    def _reset_root_dir(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)
        self._root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self._root / session_id

    def register_files(self, session_id: str, files: List[StoredSessionFile]) -> None:
        with self._lock:
            existing = self._files_by_session.setdefault(session_id, [])
            existing.extend(files)

    def get_session_files(self, session_id: str) -> List[StoredSessionFile]:
        with self._lock:
            files = self._files_by_session.get(session_id, [])
            return list(files)

    def delete_session_files(self, session_id: str) -> int:
        with self._lock:
            files = self._files_by_session.pop(session_id, [])

        deleted = 0
        for file in files:
            path = Path(file.path)
            if path.exists():
                path.unlink(missing_ok=True)
                deleted += 1

        shutil.rmtree(self.session_dir(session_id), ignore_errors=True)
        return deleted
