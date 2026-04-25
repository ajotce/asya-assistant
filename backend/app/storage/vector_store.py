from __future__ import annotations

import math
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List


@dataclass
class StoredChunkVector:
    chunk_id: str
    file_id: str
    filename: str
    text: str
    embedding: list[float]


class SessionVectorStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._chunks_by_session: Dict[str, List[StoredChunkVector]] = {}

    def upsert_file_chunks(self, session_id: str, file_id: str, chunks: List[StoredChunkVector]) -> None:
        with self._lock:
            existing = self._chunks_by_session.get(session_id, [])
            remaining = [chunk for chunk in existing if chunk.file_id != file_id]
            remaining.extend(chunks)
            self._chunks_by_session[session_id] = remaining

    def delete_file_chunks(self, session_id: str, file_id: str) -> int:
        with self._lock:
            existing = self._chunks_by_session.get(session_id, [])
            filtered = [chunk for chunk in existing if chunk.file_id != file_id]
            removed_count = len(existing) - len(filtered)
            if filtered:
                self._chunks_by_session[session_id] = filtered
            elif session_id in self._chunks_by_session:
                self._chunks_by_session.pop(session_id, None)
            return removed_count

    def search(self, session_id: str, query_embedding: list[float], top_k: int = 4) -> List[StoredChunkVector]:
        with self._lock:
            chunks = list(self._chunks_by_session.get(session_id, []))

        if not chunks:
            return []
        ranked = sorted(
            chunks,
            key=lambda item: self._cosine_similarity(query_embedding, item.embedding),
            reverse=True,
        )
        return ranked[:top_k]

    def has_session_chunks(self, session_id: str) -> bool:
        with self._lock:
            return bool(self._chunks_by_session.get(session_id))

    def delete_session(self, session_id: str) -> int:
        with self._lock:
            removed = self._chunks_by_session.pop(session_id, [])
            return len(removed)

    @staticmethod
    def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return -1.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        if n1 == 0 or n2 == 0:
            return -1.0
        return dot / (n1 * n2)
