from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.db.models.user_voice_settings import UserVoiceSettings
from app.models.schemas import (
    VoiceSettingsResponse,
    VoiceSettingsUpdateRequest,
    VoiceSTTResponse,
    VoiceTTSRequest,
)
from app.services.user_voice_settings_service import UserVoiceSettingsService
from app.voice.service import (
    VoiceService,
    VoiceValidationError,
    parse_voice_gender,
    parse_voice_provider,
)

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)


def _settings_response(settings: UserVoiceSettings) -> VoiceSettingsResponse:
    return VoiceSettingsResponse(
        assistant_name=settings.assistant_name,
        voice_gender=settings.voice_gender.value,
        stt_provider=settings.stt_provider.value,
        tts_provider=settings.tts_provider.value,
        tts_enabled=settings.tts_enabled,
    )


@router.get("/voice/settings", response_model=VoiceSettingsResponse)
def get_voice_settings(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> VoiceSettingsResponse:
    service = UserVoiceSettingsService(db_session, get_settings())
    settings = service.get_or_create(user=current_user)
    return _settings_response(settings)


@router.put("/voice/settings", response_model=VoiceSettingsResponse)
def update_voice_settings(
    request: VoiceSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> VoiceSettingsResponse:
    service = UserVoiceSettingsService(db_session, get_settings())
    try:
        settings = service.update(
            user=current_user,
            assistant_name=request.assistant_name,
            voice_gender=parse_voice_gender(request.voice_gender),
            stt_provider=parse_voice_provider(request.stt_provider),
            tts_provider=parse_voice_provider(request.tts_provider),
            tts_enabled=request.tts_enabled,
        )
    except VoiceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _settings_response(settings)


@router.post("/voice/stt", response_model=VoiceSTTResponse)
async def voice_stt(
    request: Request,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> VoiceSTTResponse:
    settings = get_settings()
    body = await request.body()
    if len(body) > settings.voice_max_audio_bytes:
        raise HTTPException(status_code=400, detail="Размер аудио превышает допустимый лимит.")

    content_type = request.headers.get("content-type", "audio/webm")
    import re

    mime_type = re.sub(r";.*", "", content_type).strip() or "audio/webm"

    voice_settings = UserVoiceSettingsService(db_session, settings)
    voice_service = VoiceService(settings, voice_settings)
    try:
        result = voice_service.transcribe(user=current_user, audio_bytes=body, mime_type=mime_type)
    except VoiceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VoiceSTTResponse(text=result.text, provider=result.provider)


@router.post("/voice/tts", response_class=Response)
def voice_tts(
    request_body: VoiceTTSRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    voice_settings = UserVoiceSettingsService(db_session, settings)
    voice_service = VoiceService(settings, voice_settings)
    try:
        result = voice_service.synthesize(user=current_user, text=request_body.text)
    except VoiceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=result.audio_bytes, media_type=result.mime_type)
