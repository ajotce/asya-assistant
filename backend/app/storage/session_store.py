from threading import Lock
from typing import Dict, List


class SessionStore:
    def __init__(self) -> None:
        self._messages: Dict[str, List[dict]] = {}
        self._lock = Lock()

    def get_messages(self, session_id: str) -> List[dict]:
        with self._lock:
            return list(self._messages.get(session_id, []))

    def append_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            if session_id not in self._messages:
                self._messages[session_id] = []
            self._messages[session_id].append({"role": role, "content": content})
