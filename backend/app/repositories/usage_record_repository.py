from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from app.db.models.usage_record import UsageRecord


class UsageRecordAggregate:
    def __init__(
        self,
        *,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
        requests_count: int,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.requests_count = requests_count


class UsageRecordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: str,
        chat_id: str | None,
        kind: str,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
    ) -> UsageRecord:
        item = UsageRecord(
            user_id=user_id,
            chat_id=chat_id,
            kind=kind,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def aggregate_for_user(self, *, user_id: str, kind: str) -> UsageRecordAggregate:
        return self._aggregate(
            and_(UsageRecord.user_id == user_id, UsageRecord.kind == kind)
        )

    def aggregate_for_chat_user(self, *, user_id: str, chat_id: str, kind: str) -> UsageRecordAggregate:
        return self._aggregate(
            and_(UsageRecord.user_id == user_id, UsageRecord.chat_id == chat_id, UsageRecord.kind == kind)
        )

    def delete_for_chat_user(self, *, user_id: str, chat_id: str) -> int:
        stmt = delete(UsageRecord).where(UsageRecord.user_id == user_id, UsageRecord.chat_id == chat_id)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def _aggregate(self, where_clause) -> UsageRecordAggregate:
        stmt = select(
            func.count(UsageRecord.id),
            func.sum(UsageRecord.prompt_tokens),
            func.sum(UsageRecord.completion_tokens),
            func.sum(UsageRecord.total_tokens),
        ).where(where_clause)
        count, prompt_sum, completion_sum, total_sum = self._session.execute(stmt).one()
        return UsageRecordAggregate(
            prompt_tokens=int(prompt_sum) if prompt_sum is not None else None,
            completion_tokens=int(completion_sum) if completion_sum is not None else None,
            total_tokens=int(total_sum) if total_sum is not None else None,
            requests_count=int(count or 0),
        )
