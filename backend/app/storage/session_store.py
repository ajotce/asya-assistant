from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List
from uuid import uuid4


@dataclass
class SessionData:
    session_id: str
    created_at: str
    messages: List[dict] = field(default_factory=list)
    file_ids: List[str] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionData] = {}
        self._lock = Lock()

    def create_session(self) -> SessionData:
        session_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        data = SessionData(session_id=session_id, created_at=created_at)
        with self._lock:
            self._sessions[session_id] = data
        return self.get_session(session_id)

    def has_session(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def get_session(self, session_id: str) -> SessionData | None:
        with self._lock:
            data = self._sessions.get(session_id)
            if data is None:
                return None
            return SessionData(
                session_id=data.session_id,
                created_at=data.created_at,
                messages=list(data.messages),
                file_ids=list(data.file_ids),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def get_messages(self, session_id: str) -> List[dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return []
            return list(session.messages)

    def append_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.messages.append({"role": role, "content": content})

    def bind_file(self, session_id: str, file_id: str) -> SessionData | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if file_id not in session.file_ids:
                session.file_ids.append(file_id)
            return SessionData(
                session_id=session.session_id,
                created_at=session.created_at,
                messages=list(session.messages),
                file_ids=list(session.file_ids),
            )

    def active_sessions_count(self) -> int:
        with self._lock:
            return len(self._sessions)
