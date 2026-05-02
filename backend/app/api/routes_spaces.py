from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.space_memory_settings import SpaceMemorySettings
from app.db.models.user import User
from app.models.schemas import (
    SpaceCreateRequest,
    SpaceListItemResponse,
    SpaceMemorySettingsResponse,
    SpaceMemorySettingsUpdateRequest,
    SpaceRenameRequest,
)
from app.services.space_service import (
    ProtectedSpaceError,
    SpaceNotFoundError,
    SpaceService,
    SpaceValidationError,
)

router = APIRouter(tags=["spaces"])


def _to_space_response(item) -> SpaceListItemResponse:
    return SpaceListItemResponse(
        id=item.id,
        name=item.name,
        is_default=item.is_default,
        is_admin_only=item.is_admin_only,
        is_archived=item.is_archived,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _to_settings_response(item: SpaceMemorySettings) -> SpaceMemorySettingsResponse:
    return SpaceMemorySettingsResponse(
        space_id=item.space_id,
        memory_read_enabled=item.memory_read_enabled,
        memory_write_enabled=item.memory_write_enabled,
        behavior_rules_enabled=item.behavior_rules_enabled,
        personality_overlay_enabled=item.personality_overlay_enabled,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/spaces", response_model=list[SpaceListItemResponse])
def list_spaces(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[SpaceListItemResponse]:
    items = SpaceService(db_session).list_spaces(current_user)
    return [_to_space_response(item) for item in items]


@router.post("/spaces", response_model=SpaceListItemResponse, status_code=status.HTTP_201_CREATED)
def create_space(
    payload: SpaceCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SpaceListItemResponse:
    service = SpaceService(db_session)
    try:
        item = service.create_space(user=current_user, name=payload.name)
    except SpaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_space_response(item)


@router.patch("/spaces/{space_id}", response_model=SpaceListItemResponse)
def rename_space(
    space_id: str,
    payload: SpaceRenameRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SpaceListItemResponse:
    service = SpaceService(db_session)
    try:
        item = service.rename_space(user=current_user, space_id=space_id, name=payload.name)
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SpaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProtectedSpaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_space_response(item)


@router.post("/spaces/{space_id}/archive", response_model=SpaceListItemResponse)
def archive_space(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SpaceListItemResponse:
    service = SpaceService(db_session)
    try:
        item = service.archive_space(user=current_user, space_id=space_id)
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProtectedSpaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_space_response(item)


@router.get("/spaces/{space_id}/settings", response_model=SpaceMemorySettingsResponse)
def get_space_settings(
    space_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SpaceMemorySettingsResponse:
    service = SpaceService(db_session)
    try:
        settings = service.get_space_settings(user=current_user, space_id=space_id)
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_settings_response(settings)


@router.put("/spaces/{space_id}/settings", response_model=SpaceMemorySettingsResponse)
def update_space_settings(
    space_id: str,
    payload: SpaceMemorySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SpaceMemorySettingsResponse:
    service = SpaceService(db_session)
    try:
        settings = service.update_space_settings(
            user=current_user,
            space_id=space_id,
            memory_read_enabled=payload.memory_read_enabled,
            memory_write_enabled=payload.memory_write_enabled,
            behavior_rules_enabled=payload.behavior_rules_enabled,
            personality_overlay_enabled=payload.personality_overlay_enabled,
        )
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_settings_response(settings)
