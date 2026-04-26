from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.services.vsellm_client import ReasoningProbeResult


class ReasoningProbeCache:
    def __init__(self, ttl_seconds: int = 24 * 3600) -> None:
        self._ttl_seconds = ttl_seconds
        self._items: dict[str, ReasoningProbeResult] = {}

    def get(self, model_id: str) -> Optional[ReasoningProbeResult]:
        item = self._items.get(model_id)
        if item is None or self._is_expired(item):
            return None
        return item

    def set(self, result: ReasoningProbeResult) -> None:
        self._items[result.model_id] = result

    def all_fresh(self) -> list[ReasoningProbeResult]:
        return [item for item in self._items.values() if not self._is_expired(item)]

    def reset(self) -> None:
        self._items.clear()

    def _is_expired(self, item: ReasoningProbeResult) -> bool:
        age = (datetime.now(timezone.utc) - item.checked_at).total_seconds()
        return age > self._ttl_seconds
