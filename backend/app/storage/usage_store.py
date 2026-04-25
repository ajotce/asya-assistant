from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional


@dataclass
class ChatUsageAggregate:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    requests_count: int = 0


@dataclass
class EmbeddingsUsageAggregate:
    input_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    requests_count: int = 0


class UsageStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._chat_total = ChatUsageAggregate()
        self._embeddings_total = EmbeddingsUsageAggregate()
        self._chat_by_session: Dict[str, ChatUsageAggregate] = {}
        self._embeddings_by_session: Dict[str, EmbeddingsUsageAggregate] = {}

    def record_chat_usage(self, session_id: str, usage: dict | None) -> None:
        if not isinstance(usage, dict):
            return

        prompt_tokens = self._extract_int(usage.get("prompt_tokens"))
        if prompt_tokens is None:
            prompt_tokens = self._extract_int(usage.get("input_tokens"))

        completion_tokens = self._extract_int(usage.get("completion_tokens"))
        if completion_tokens is None:
            completion_tokens = self._extract_int(usage.get("output_tokens"))

        total_tokens = self._extract_int(usage.get("total_tokens"))
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        with self._lock:
            self._chat_total = self._merge_chat(self._chat_total, prompt_tokens, completion_tokens, total_tokens)
            session_value = self._chat_by_session.get(session_id, ChatUsageAggregate())
            self._chat_by_session[session_id] = self._merge_chat(session_value, prompt_tokens, completion_tokens, total_tokens)

    def record_embeddings_usage(self, session_id: str, usage: dict | None) -> None:
        if not isinstance(usage, dict):
            return

        input_tokens = self._extract_int(usage.get("input_tokens"))
        if input_tokens is None:
            input_tokens = self._extract_int(usage.get("prompt_tokens"))

        total_tokens = self._extract_int(usage.get("total_tokens"))
        if total_tokens is None and input_tokens is not None:
            total_tokens = input_tokens

        with self._lock:
            self._embeddings_total = self._merge_embeddings(self._embeddings_total, input_tokens, total_tokens)
            session_value = self._embeddings_by_session.get(session_id, EmbeddingsUsageAggregate())
            self._embeddings_by_session[session_id] = self._merge_embeddings(session_value, input_tokens, total_tokens)

    def get_chat_total(self) -> ChatUsageAggregate:
        with self._lock:
            value = self._chat_total
            return ChatUsageAggregate(
                prompt_tokens=value.prompt_tokens,
                completion_tokens=value.completion_tokens,
                total_tokens=value.total_tokens,
                requests_count=value.requests_count,
            )

    def get_embeddings_total(self) -> EmbeddingsUsageAggregate:
        with self._lock:
            value = self._embeddings_total
            return EmbeddingsUsageAggregate(
                input_tokens=value.input_tokens,
                total_tokens=value.total_tokens,
                requests_count=value.requests_count,
            )

    def get_chat_for_session(self, session_id: str) -> ChatUsageAggregate:
        with self._lock:
            value = self._chat_by_session.get(session_id, ChatUsageAggregate())
            return ChatUsageAggregate(
                prompt_tokens=value.prompt_tokens,
                completion_tokens=value.completion_tokens,
                total_tokens=value.total_tokens,
                requests_count=value.requests_count,
            )

    def get_embeddings_for_session(self, session_id: str) -> EmbeddingsUsageAggregate:
        with self._lock:
            value = self._embeddings_by_session.get(session_id, EmbeddingsUsageAggregate())
            return EmbeddingsUsageAggregate(
                input_tokens=value.input_tokens,
                total_tokens=value.total_tokens,
                requests_count=value.requests_count,
            )

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._chat_by_session.pop(session_id, None)
            self._embeddings_by_session.pop(session_id, None)

    def reset(self) -> None:
        with self._lock:
            self._chat_total = ChatUsageAggregate()
            self._embeddings_total = EmbeddingsUsageAggregate()
            self._chat_by_session = {}
            self._embeddings_by_session = {}

    @staticmethod
    def _merge_chat(
        current: ChatUsageAggregate,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
    ) -> ChatUsageAggregate:
        return ChatUsageAggregate(
            prompt_tokens=UsageStore._add_optional(current.prompt_tokens, prompt_tokens),
            completion_tokens=UsageStore._add_optional(current.completion_tokens, completion_tokens),
            total_tokens=UsageStore._add_optional(current.total_tokens, total_tokens),
            requests_count=current.requests_count + 1,
        )

    @staticmethod
    def _merge_embeddings(
        current: EmbeddingsUsageAggregate,
        input_tokens: Optional[int],
        total_tokens: Optional[int],
    ) -> EmbeddingsUsageAggregate:
        return EmbeddingsUsageAggregate(
            input_tokens=UsageStore._add_optional(current.input_tokens, input_tokens),
            total_tokens=UsageStore._add_optional(current.total_tokens, total_tokens),
            requests_count=current.requests_count + 1,
        )

    @staticmethod
    def _add_optional(current: Optional[int], value: Optional[int]) -> Optional[int]:
        if value is None:
            return current
        if current is None:
            return value
        return current + value

    @staticmethod
    def _extract_int(value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(float(stripped))
            except ValueError:
                return None
        return None
