from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.integrations.telegram.bot_sender import TelegramBotSender
from app.integrations.telegram.link_service import TelegramLinkError, TelegramLinkService
from app.integrations.telegram.notification_channel import TelegramNotificationChannel
from app.models.schemas import TelegramLinkStatusResponse, TelegramLinkTokenResponse, TelegramUnlinkResponse
from app.notifications.notification_center import NotificationCenter

router = APIRouter(tags=["telegram"])


class TelegramTestNotificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Asya")
    body: str = Field(min_length=1, max_length=1000)


@router.get("/integrations/telegram/status", response_model=TelegramLinkStatusResponse)
def telegram_status(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> TelegramLinkStatusResponse:
    service = TelegramLinkService(db_session, get_settings())
    status = service.status(user=current_user)
    return TelegramLinkStatusResponse(
        is_linked=status.is_linked,
        telegram_user_id=status.telegram_user_id,
        telegram_username=status.telegram_username,
        telegram_chat_id=status.telegram_chat_id,
    )


@router.post("/integrations/telegram/link-token", response_model=TelegramLinkTokenResponse)
def create_link_token(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> TelegramLinkTokenResponse:
    service = TelegramLinkService(db_session, get_settings())
    try:
        token = service.create_one_time_token(user=current_user)
    except TelegramLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TelegramLinkTokenResponse(
        one_time_token=token.one_time_token,
        expires_at=token.expires_at.isoformat(),
        bot_start_url=token.bot_start_url,
    )


@router.post("/integrations/telegram/unlink", response_model=TelegramUnlinkResponse)
def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> TelegramUnlinkResponse:
    service = TelegramLinkService(db_session, get_settings())
    unlinked = service.unlink(user=current_user)
    return TelegramUnlinkResponse(status="ok", unlinked=unlinked)


class NotifyTestResponse(BaseModel):
    status: str


@router.post("/integrations/telegram/notify-test", response_model=NotifyTestResponse)
def notify_test(
    request: TelegramTestNotificationRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    sender = TelegramBotSender(db_session, get_settings())
    center = NotificationCenter(db_session, channels=[TelegramNotificationChannel(sender)])
    center.notify_user(
        current_user,
        title=request.title,
        body=request.body,
        channel="telegram",
        metadata={"kind": "test"},
    )
    return {"status": "ok"}
