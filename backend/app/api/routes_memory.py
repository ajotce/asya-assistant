from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import (
    ActivityEntityType,
    ActivityEventType,
    MemoryStatus,
    RuleScope,
    RuleSource,
    RuleStatus,
    RuleStrictness,
)
from app.db.models.user import User
from app.models.schemas import (
    ActivityLogItemResponse,
    BehaviorRuleCreateRequest,
    BehaviorRuleItemResponse,
    BehaviorRuleUpdateRequest,
    MemoryChangeItemResponse,
    MemoryEpisodeItemResponse,
    MemoryFactCreateRequest,
    MemoryFactItemResponse,
    MemoryFactStatusUpdateRequest,
    MemoryFactUpdateRequest,
    MemorySnapshotCreateRequest,
    MemorySnapshotItemResponse,
    MemorySnapshotSummaryResponse,
    PersonalityProfileResponse,
    PersonalityProfileUpdateRequest,
)
from app.services.memory_service import (
    FactCreatePayload,
    MemoryNotFoundError,
    MemoryService,
    MemoryValidationError,
    RuleCreatePayload,
)

router = APIRouter(tags=["memory"])


def _parse_memory_status(raw: str) -> MemoryStatus:
    try:
        return MemoryStatus(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый статус памяти.") from exc


def _parse_rule_scope(raw: str) -> RuleScope:
    try:
        return RuleScope(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый scope правила.") from exc


def _parse_rule_strictness(raw: str) -> RuleStrictness:
    try:
        return RuleStrictness(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемая strictness правила.") from exc


def _parse_rule_source(raw: str) -> RuleSource:
    try:
        return RuleSource(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый source правила.") from exc


def _parse_rule_status(raw: str) -> RuleStatus:
    try:
        return RuleStatus(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый status правила.") from exc


def _parse_activity_event_type(raw: str) -> ActivityEventType:
    try:
        return ActivityEventType(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый тип события активности.") from exc


def _parse_activity_entity_type(raw: str) -> ActivityEntityType:
    try:
        return ActivityEntityType(raw)
    except ValueError as exc:
        raise MemoryValidationError("Неподдерживаемый тип сущности активности.") from exc


def _parse_optional_datetime(raw: Optional[str], field_name: str) -> Optional[datetime]:
    if raw is None:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise MemoryValidationError(f"Некорректная дата в параметре {field_name}.") from exc


def _fact_out(item) -> MemoryFactItemResponse:
    return MemoryFactItemResponse(
        id=item.id,
        key=item.key,
        value=item.value,
        status=item.status.value,
        source=item.source,
        space_id=item.space_id,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _rule_out(item) -> BehaviorRuleItemResponse:
    return BehaviorRuleItemResponse(
        id=item.id,
        title=item.title,
        instruction=item.instruction,
        scope=item.scope.value,
        strictness=item.strictness.value,
        source=item.source.value,
        status=item.status.value,
        space_id=item.space_id,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/memory/facts", response_model=list[MemoryFactItemResponse])
def list_facts(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    items = MemoryService(db_session).list_facts(user=current_user, active_only=active_only)
    return [_fact_out(item) for item in items]


@router.post("/memory/facts", response_model=MemoryFactItemResponse)
def create_fact(
    payload: MemoryFactCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.create_fact(
            user=current_user,
            payload=FactCreatePayload(
                key=payload.key,
                value=payload.value,
                status=_parse_memory_status(payload.status),
                source=payload.source,
                space_id=payload.space_id,
            ),
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _fact_out(item)


@router.patch("/memory/facts/{fact_id}", response_model=MemoryFactItemResponse)
def update_fact(
    fact_id: str,
    payload: MemoryFactUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.update_fact(user=current_user, fact_id=fact_id, key=payload.key, value=payload.value, source=payload.source)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _fact_out(item)


@router.post("/memory/facts/{fact_id}/status", response_model=MemoryFactItemResponse)
def update_fact_status(
    fact_id: str,
    payload: MemoryFactStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.set_fact_status(user=current_user, fact_id=fact_id, status=_parse_memory_status(payload.status))
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _fact_out(item)


@router.post("/memory/facts/{fact_id}/forbid", response_model=MemoryFactItemResponse)
def forbid_fact(
    fact_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.forbid_fact(user=current_user, fact_id=fact_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _fact_out(item)


@router.get("/memory/rules", response_model=list[BehaviorRuleItemResponse])
def list_rules(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    items = MemoryService(db_session).list_rules(user=current_user, active_only=active_only)
    return [_rule_out(item) for item in items]


@router.post("/memory/rules", response_model=BehaviorRuleItemResponse)
def create_rule(
    payload: BehaviorRuleCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.create_rule(
            user=current_user,
            payload=RuleCreatePayload(
                title=payload.title,
                instruction=payload.instruction,
                scope=_parse_rule_scope(payload.scope),
                strictness=_parse_rule_strictness(payload.strictness),
                source=_parse_rule_source(payload.source),
                status=_parse_rule_status(payload.status),
                space_id=payload.space_id,
            ),
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _rule_out(item)


@router.patch("/memory/rules/{rule_id}", response_model=BehaviorRuleItemResponse)
def update_rule(
    rule_id: str,
    payload: BehaviorRuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.update_rule(
            user=current_user,
            rule_id=rule_id,
            title=payload.title,
            instruction=payload.instruction,
            scope=_parse_rule_scope(payload.scope),
            strictness=_parse_rule_strictness(payload.strictness),
            source=_parse_rule_source(payload.source),
            status=_parse_rule_status(payload.status),
            space_id=payload.space_id,
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _rule_out(item)


@router.post("/memory/rules/{rule_id}/disable", response_model=BehaviorRuleItemResponse)
def disable_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.disable_rule(user=current_user, rule_id=rule_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _rule_out(item)


@router.get("/memory/episodes", response_model=list[MemoryEpisodeItemResponse])
def list_episodes(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    items = MemoryService(db_session).list_episodes(user=current_user, active_only=active_only)
    return [
        MemoryEpisodeItemResponse(
            id=item.id,
            chat_id=item.chat_id,
            summary=item.summary,
            status=item.status.value,
            source=item.source,
            space_id=item.space_id,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )
        for item in items
    ]


@router.get("/memory/changes", response_model=list[MemoryChangeItemResponse])
def list_changes(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    items = MemoryService(db_session).list_changes(user=current_user)
    return [
        MemoryChangeItemResponse(
            id=item.id,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            change_kind=item.change_kind.value,
            old_value=item.old_value,
            new_value=item.new_value,
            space_id=item.space_id,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]


@router.get("/activity-log", response_model=list[ActivityLogItemResponse])
def list_activity_log(
    limit: int = 100,
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    space_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        parsed_event_type = _parse_activity_event_type(event_type) if event_type else None
        parsed_entity_type = _parse_activity_entity_type(entity_type) if entity_type else None
        parsed_date_from = _parse_optional_datetime(date_from, "date_from")
        parsed_date_to = _parse_optional_datetime(date_to, "date_to")
        items = service.list_activity(
            user=current_user,
            limit=limit,
            event_type=parsed_event_type,
            entity_type=parsed_entity_type,
            space_id=space_id,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        ActivityLogItemResponse(
            id=item.id,
            event_type=item.event_type.value,
            entity_type=item.entity_type.value,
            entity_id=item.entity_id,
            summary=item.summary,
            meta=item.meta,
            space_id=item.space_id,
            created_at=item.created_at.isoformat(),
        )
        for item in items
    ]


@router.post("/memory/snapshots", response_model=MemorySnapshotItemResponse)
def create_memory_snapshot(
    payload: MemorySnapshotCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.create_snapshot(user=current_user, label=payload.label, space_id=payload.space_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemorySnapshotItemResponse(
        id=item.id,
        label=item.label,
        space_id=item.space_id,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/memory/snapshots", response_model=list[MemorySnapshotItemResponse])
def list_memory_snapshots(
    space_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        items = service.list_snapshots(user=current_user, space_id=space_id, limit=limit)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        MemorySnapshotItemResponse(
            id=item.id,
            label=item.label,
            space_id=item.space_id,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )
        for item in items
    ]


@router.get("/memory/snapshots/{snapshot_id}", response_model=MemorySnapshotSummaryResponse)
def get_memory_snapshot_summary(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        summary = service.get_snapshot_summary(user=current_user, snapshot_id=snapshot_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MemorySnapshotSummaryResponse(**summary)


@router.post("/memory/snapshots/{snapshot_id}/rollback", response_model=MemorySnapshotItemResponse)
def rollback_memory_snapshot(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.rollback_to_snapshot(user=current_user, snapshot_id=snapshot_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemorySnapshotItemResponse(
        id=item.id,
        label=item.label,
        space_id=item.space_id,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/personality", response_model=PersonalityProfileResponse)
def get_personality(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    item = MemoryService(db_session).get_or_create_personality(user=current_user)
    return _personality_out(item)


@router.put("/personality", response_model=PersonalityProfileResponse)
def update_personality(
    payload: PersonalityProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    item = MemoryService(db_session).update_personality(
        user=current_user,
        name=payload.name,
        tone=payload.tone,
        style_notes=payload.style_notes,
        humor_level=payload.humor_level,
        initiative_level=payload.initiative_level,
        can_gently_disagree=payload.can_gently_disagree,
        address_user_by_name=payload.address_user_by_name,
        is_active=payload.is_active,
    )
    return _personality_out(item)


@router.get("/personality/overlay/{space_id}", response_model=PersonalityProfileResponse)
def get_personality_overlay(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.get_or_create_personality_overlay(user=current_user, space_id=space_id)
    except MemoryValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _personality_out(item)


@router.put("/personality/overlay/{space_id}", response_model=PersonalityProfileResponse)
def update_personality_overlay(
    space_id: str,
    payload: PersonalityProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = MemoryService(db_session)
    try:
        item = service.update_personality_overlay(
            user=current_user,
            space_id=space_id,
            name=payload.name,
            tone=payload.tone,
            style_notes=payload.style_notes,
            humor_level=payload.humor_level,
            initiative_level=payload.initiative_level,
            can_gently_disagree=payload.can_gently_disagree,
            address_user_by_name=payload.address_user_by_name,
            is_active=payload.is_active,
        )
    except MemoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _personality_out(item)
def _personality_out(item) -> PersonalityProfileResponse:
    return PersonalityProfileResponse(
        id=item.id,
        scope=item.scope.value,
        space_id=item.space_id,
        name=item.name,
        tone=item.tone,
        style_notes=item.style_notes,
        humor_level=item.humor_level,
        initiative_level=item.initiative_level,
        can_gently_disagree=item.can_gently_disagree,
        address_user_by_name=item.address_user_by_name,
        is_active=item.is_active,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
