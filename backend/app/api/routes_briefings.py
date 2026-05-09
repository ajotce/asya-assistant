from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import BriefingKind
from app.db.models.user import User
from app.models.schemas import (
    BriefingItemResponse,
    BriefingSettingsPatchRequest,
    BriefingSettingsResponse,
)
from app.services.briefing_service import BriefingNotFoundError, BriefingService, BriefingSettingsPatch

router = APIRouter(tags=["briefings"])


def _to_item_response(item) -> BriefingItemResponse:
    return BriefingItemResponse(
        id=item.id,
        user_id=item.user_id,
        kind=item.kind.value,
        content=item.content,
        delivered_via=item.delivered_via,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _to_settings_response(item) -> BriefingSettingsResponse:
    return BriefingSettingsResponse(
        timezone=item.timezone,
        morning_enabled=item.morning_enabled,
        evening_enabled=item.evening_enabled,
        morning_time=item.morning_time,
        evening_time=item.evening_time,
        channel_in_app=item.channel_in_app,
        channel_telegram=item.channel_telegram,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/briefings", response_model=list[BriefingItemResponse])
def list_briefings(
    days: int = 30,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[BriefingItemResponse]:
    items = BriefingService(db_session).list_recent(user_id=current_user.id, days=days, limit=limit)
    return [_to_item_response(item) for item in items]


@router.get("/briefings/{briefing_id}", response_model=BriefingItemResponse)
def get_briefing(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingItemResponse:
    service = BriefingService(db_session)
    try:
        item = service.get_by_id(user_id=current_user.id, briefing_id=briefing_id)
    except BriefingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_item_response(item)


@router.post("/briefings/generate", response_model=BriefingItemResponse)
def generate_briefing(
    kind: str = "morning",
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingItemResponse:
    try:
        parsed_kind = BriefingKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный тип briefing") from exc
    item = BriefingService(db_session).generate(user_id=current_user.id, kind=parsed_kind)
    return _to_item_response(item)


@router.get("/briefings/settings", response_model=BriefingSettingsResponse)
def get_briefing_settings(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingSettingsResponse:
    item = BriefingService(db_session).get_settings(current_user)
    return _to_settings_response(item)


@router.patch("/briefings/settings", response_model=BriefingSettingsResponse)
def patch_briefing_settings(
    payload: BriefingSettingsPatchRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingSettingsResponse:
    service = BriefingService(db_session)
    try:
        item = service.patch_settings(
            current_user,
            BriefingSettingsPatch(
                timezone=payload.timezone,
                morning_enabled=payload.morning_enabled,
                evening_enabled=payload.evening_enabled,
                morning_time=payload.morning_time,
                evening_time=payload.evening_time,
                channel_in_app=payload.channel_in_app,
                channel_telegram=payload.channel_telegram,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_settings_response(item)
