from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.integrations.telegram.bot_sender import TelegramBotSender
from app.models.schemas import (
    BriefingArchiveItemResponse,
    BriefingGenerateRequest,
    BriefingItemResponse,
    BriefingSettingsPatchRequest,
    BriefingSettingsResponse,
)
from app.services.briefing_service import BriefingNotFoundError, BriefingService, BriefingSettingsPatch

router = APIRouter(tags=["briefings"])


class BriefingGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    briefing: BriefingItemResponse


@router.get("/briefings/settings", response_model=BriefingSettingsResponse)
def get_briefing_settings(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingSettingsResponse:
    item = BriefingService(db_session).get_settings(current_user)
    return BriefingSettingsResponse(
        morning_enabled=item.morning_enabled,
        evening_enabled=item.evening_enabled,
        delivery_in_app=item.delivery_in_app,
        delivery_telegram=item.delivery_telegram,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.patch("/briefings/settings", response_model=BriefingSettingsResponse)
def patch_briefing_settings(
    payload: BriefingSettingsPatchRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingSettingsResponse:
    item = BriefingService(db_session).patch_settings(
        current_user,
        BriefingSettingsPatch(
            morning_enabled=payload.morning_enabled,
            evening_enabled=payload.evening_enabled,
            delivery_in_app=payload.delivery_in_app,
            delivery_telegram=payload.delivery_telegram,
        ),
    )
    return BriefingSettingsResponse(
        morning_enabled=item.morning_enabled,
        evening_enabled=item.evening_enabled,
        delivery_in_app=item.delivery_in_app,
        delivery_telegram=item.delivery_telegram,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.post("/briefings/generate", response_model=BriefingGenerateResponse)
def generate_briefing(
    payload: BriefingGenerateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingGenerateResponse:
    settings = get_settings()
    item = BriefingService(db_session).generate_manual(
        user=current_user,
        kind=payload.kind,
        app_base_url=settings.public_base_url,
        telegram_sender=TelegramBotSender(db_session, settings),
    )
    return BriefingGenerateResponse(
        status="ok",
        briefing=BriefingItemResponse(
            id=item.id,
            kind=item.kind,
            title=item.title,
            content_markdown=item.content_markdown,
            delivered_in_app=item.delivered_in_app,
            delivered_telegram=item.delivered_telegram,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        ),
    )


@router.get("/briefings/archive", response_model=list[BriefingArchiveItemResponse])
def list_archive(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[BriefingArchiveItemResponse]:
    rows = BriefingService(db_session).list_archive(current_user, limit=limit)
    return [
        BriefingArchiveItemResponse(
            id=item.id,
            kind=item.kind,
            title=item.title,
            delivered_in_app=item.delivered_in_app,
            delivered_telegram=item.delivered_telegram,
            created_at=item.created_at.isoformat(),
        )
        for item in rows
    ]


@router.get("/briefings/{briefing_id}", response_model=BriefingItemResponse)
def get_briefing_item(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> BriefingItemResponse:
    try:
        item = BriefingService(db_session).get_item(current_user, briefing_id)
    except BriefingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BriefingItemResponse(
        id=item.id,
        kind=item.kind,
        title=item.title,
        content_markdown=item.content_markdown,
        delivered_in_app=item.delivered_in_app,
        delivered_telegram=item.delivered_telegram,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
