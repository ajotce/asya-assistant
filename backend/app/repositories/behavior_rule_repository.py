from __future__ import annotations

from typing import Optional

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.db.models.behavior_rule import BehaviorRule
from app.db.models.common import RuleScope, RuleStatus


class BehaviorRuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, active_only: bool = False) -> list[BehaviorRule]:
        stmt = select(BehaviorRule).where(BehaviorRule.user_id == user_id)
        if active_only:
            stmt = stmt.where(BehaviorRule.status == RuleStatus.ACTIVE)
        stmt = stmt.order_by(BehaviorRule.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, rule_id: str, user_id: str) -> Optional[BehaviorRule]:
        stmt = select(BehaviorRule).where(BehaviorRule.id == rule_id, BehaviorRule.user_id == user_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def create(self, *, user_id: str, space_id: str | None, scope, strictness, status, source, title: str, instruction: str) -> BehaviorRule:
        item = BehaviorRule(
            user_id=user_id,
            space_id=space_id,
            scope=scope,
            strictness=strictness,
            status=status,
            source=source,
            title=title,
            instruction=instruction,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def save(self, item: BehaviorRule) -> BehaviorRule:
        self._session.add(item)
        self._session.flush()
        return item

    def list_active_for_user_space(self, *, user_id: str, space_id: str | None, limit: int = 12) -> list[BehaviorRule]:
        scoped_space_rule = false()
        if space_id is not None:
            scoped_space_rule = (BehaviorRule.scope == RuleScope.SPACE) & (BehaviorRule.space_id == space_id)
        stmt = (
            select(BehaviorRule)
            .where(
                BehaviorRule.user_id == user_id,
                BehaviorRule.status == RuleStatus.ACTIVE,
                or_(
                    BehaviorRule.scope.in_([RuleScope.GLOBAL, RuleScope.USER]),
                    scoped_space_rule,
                ),
            )
            .order_by(BehaviorRule.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
