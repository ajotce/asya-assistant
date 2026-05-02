from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.models.common import MemoryStatus, RuleScope, RuleSource, RuleStatus, RuleStrictness
from app.db.models.user import User
from app.services.memory_service import FactCreatePayload, MemoryService, RuleCreatePayload


@dataclass
class ExtractionResult:
    created_facts: int = 0
    updated_facts: int = 0
    created_rules: int = 0
    created_episodes: int = 0


class MemoryExtractionService:
    _EXPLICIT_REMEMBER_RE = re.compile(r"\bзапомни\b", flags=re.IGNORECASE)
    _FORGET_RE = re.compile(r"\bзабудь\b", flags=re.IGNORECASE)
    _STYLE_RE = re.compile(r"\b(отвечай|пиши|стиль|короче|подробно)\b", flags=re.IGNORECASE)
    _DECISION_RE = re.compile(r"\b(решили|договорились|решение|выбрали)\b", flags=re.IGNORECASE)
    _RULE_SAVE_RE = re.compile(r"\b(сохрани|добавь|запомни)\b.*\bправил", flags=re.IGNORECASE)

    # Safety filter: never extract obvious secrets.
    _SENSITIVE_PATTERNS = [
        re.compile(r"\b(password|парол[ья]|token|токен|api[\s_-]?key|секрет|secret|cvv|cvc)\b", re.IGNORECASE),
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        re.compile(r"\b\d{16}\b"),
    ]

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory = memory_service

    def process_turn(self, *, user: User, chat_id: str, user_message: str, assistant_message: str) -> ExtractionResult:
        result = ExtractionResult()
        normalized = user_message.strip()
        if not normalized:
            return result

        if self._contains_sensitive_data(normalized):
            return result

        if self._FORGET_RE.search(normalized):
            query = self._extract_forget_query(normalized)
            facts = self._memory.list_facts(user=user, active_only=True)
            lowered_query = query.lower()
            for fact in facts:
                searchable = f"{fact.key} {fact.value}".lower()
                if lowered_query and lowered_query not in searchable:
                    continue
                self._memory.forbid_fact(user=user, fact_id=fact.id)
                result.updated_facts += 1
            return result

        if self._EXPLICIT_REMEMBER_RE.search(normalized):
            remembered = self._extract_remember_payload(normalized)
            if remembered and not self._contains_sensitive_data(remembered):
                self._memory.create_fact(
                    user=user,
                    payload=FactCreatePayload(
                        key="remembered_note",
                        value=remembered,
                        status=MemoryStatus.CONFIRMED,
                        source="user_explicit",
                        space_id=None,
                    ),
                )
                result.created_facts += 1

        inferred = self._extract_inferred_fact(normalized)
        if inferred and not self._EXPLICIT_REMEMBER_RE.search(normalized):
            self._memory.create_fact(
                user=user,
                payload=FactCreatePayload(
                    key=inferred[0],
                    value=inferred[1],
                    status=MemoryStatus.NEEDS_REVIEW,
                    source="assistant_inferred",
                    space_id=None,
                ),
            )
            result.created_facts += 1

        if self._STYLE_RE.search(normalized):
            self._memory.create_rule(
                user=user,
                payload=RuleCreatePayload(
                    title="User response style preference",
                    instruction=normalized,
                    scope=RuleScope.USER,
                    strictness=RuleStrictness.NORMAL,
                    source=RuleSource.USER,
                    status=RuleStatus.ACTIVE,
                    space_id=None,
                ),
            )
            result.created_rules += 1
        elif self._RULE_SAVE_RE.search(normalized):
            self._memory.create_rule(
                user=user,
                payload=RuleCreatePayload(
                    title="Rule after user feedback",
                    instruction=normalized[:6000],
                    scope=RuleScope.USER,
                    strictness=RuleStrictness.NORMAL,
                    source=RuleSource.USER,
                    status=RuleStatus.ACTIVE,
                    space_id=None,
                ),
            )
            result.created_rules += 1

        if self._DECISION_RE.search(normalized) or self._DECISION_RE.search(assistant_message or ""):
            self._memory.create_episode(
                user=user,
                chat_id=chat_id,
                summary=f"User: {normalized[:400]}",
                status=MemoryStatus.INFERRED,
                source="assistant_inferred",
                space_id=None,
            )
            result.created_episodes += 1

        return result

    @staticmethod
    def _extract_remember_payload(message: str) -> str:
        lowered = message.lower()
        marker = "запомни"
        idx = lowered.find(marker)
        if idx == -1:
            return ""
        payload = message[idx + len(marker) :].strip(" :,.\n\t")
        return payload

    @staticmethod
    def _extract_forget_query(message: str) -> str:
        lowered = message.lower()
        marker = "забудь"
        idx = lowered.find(marker)
        if idx == -1:
            return ""
        payload = message[idx + len(marker) :].strip(" :,.\n\t")
        return payload

    @staticmethod
    def _extract_inferred_fact(message: str) -> tuple[str, str] | None:
        lower = message.lower()
        if "меня зовут" in lower:
            return ("user_name", message)
        if "я " in lower or "мне " in lower or "мой " in lower:
            return ("user_context", message)
        return None

    def _contains_sensitive_data(self, text: str) -> bool:
        for pattern in self._SENSITIVE_PATTERNS:
            if pattern.search(text):
                return True
        return False
