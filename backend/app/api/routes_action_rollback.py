from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.models.schemas import (
    ActionEventItemResponse,
    RollbackExecuteRequest,
    RollbackExecuteResponse,
    RollbackPreviewResponse,
)
from app.repositories.action_event_repository import ActionEventRepository
from app.repositories.activity_log_repository import ActivityLogRepository
from app.services.action_rollback_service import ActionRollbackError, ActionRollbackService
from app.services.memory_service import MemoryService

router = APIRouter(tags=["action-rollback"])


def _build_service(db_session: Session) -> ActionRollbackService:
    return ActionRollbackService(
        action_events=ActionEventRepository(db_session),
        activity_logs=ActivityLogRepository(db_session),
        memory_service_factory=lambda: MemoryService(db_session),
    )


@router.get("/actions/reversible", response_model=list[ActionEventItemResponse])
def list_reversible_actions(
    limit: int = 100,
    reversible_only: bool = True,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    items = _build_service(db_session).list_actions(user_id=current_user.id, reversible_only=reversible_only, limit=limit)
    return [
        ActionEventItemResponse(
            id=item.id,
            provider=item.provider,
            operation=item.operation,
            target_id=item.target_id,
            reversible=item.reversible,
            rollback_status=item.rollback_status.value,
            rollback_strategy=item.rollback_strategy,
            rollback_deadline=item.rollback_deadline.isoformat() if item.rollback_deadline else None,
            rollback_notes=item.rollback_notes,
            previous_state=item.previous_state,
            safe_metadata=item.safe_metadata,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )
        for item in items
    ]


@router.get("/actions/{action_event_id}/rollback-preview", response_model=RollbackPreviewResponse)
def preview_rollback(
    action_event_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = _build_service(db_session)
    try:
        plan = service.preview(user_id=current_user.id, action_event_id=action_event_id)
    except ActionRollbackError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RollbackPreviewResponse(
        action_event_id=plan.action_event_id,
        provider=plan.provider,
        operation=plan.operation,
        target_id=plan.target_id,
        reversible=plan.reversible,
        rollback_strategy=plan.rollback_strategy,
        rollback_deadline=plan.rollback_deadline.isoformat() if plan.rollback_deadline else None,
        rollback_notes=plan.rollback_notes,
        previous_state=plan.previous_state,
        safe_metadata=plan.safe_metadata,
    )


@router.post("/actions/{action_event_id}/rollback", response_model=RollbackExecuteResponse)
def execute_rollback(
    action_event_id: str,
    payload: RollbackExecuteRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    service = _build_service(db_session)
    try:
        result = service.execute(user=current_user, action_event_id=action_event_id, confirmed=payload.confirmed)
        db_session.commit()
    except ActionRollbackError as exc:
        db_session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RollbackExecuteResponse(
        action_event_id=result.action_event_id,
        status=result.status.value,
        message=result.message,
    )
