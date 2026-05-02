from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.models.schemas import (
    DiaryEntryCreateRequest,
    DiaryEntryItemResponse,
    DiaryEntryUpdateRequest,
    DiarySettingsPatchRequest,
    DiarySettingsResponse,
)
from app.services.diary_service import DiaryNotFoundError, DiaryService, DiarySettingsPatch

router = APIRouter(tags=["diary"])


def _settings_out(item) -> DiarySettingsResponse:
    return DiarySettingsResponse(
        briefing_enabled=item.briefing_enabled,
        search_enabled=item.search_enabled,
        memories_enabled=item.memories_enabled,
        evening_prompt_enabled=item.evening_prompt_enabled,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _entry_out(item) -> DiaryEntryItemResponse:
    return DiaryEntryItemResponse(
        id=item.id,
        title=item.title,
        content=item.content,
        transcript=item.transcript,
        topics=item.topics,
        decisions=item.decisions,
        mentions=item.mentions,
        source_audio_path=item.source_audio_path,
        processing_status=item.processing_status,
        processing_error=item.processing_error,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/diary/settings", response_model=DiarySettingsResponse)
def get_diary_settings(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiarySettingsResponse:
    item = DiaryService(db_session).get_settings(current_user)
    return _settings_out(item)


@router.patch("/diary/settings", response_model=DiarySettingsResponse)
def patch_diary_settings(
    payload: DiarySettingsPatchRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiarySettingsResponse:
    item = DiaryService(db_session).patch_settings(
        current_user,
        DiarySettingsPatch(
            briefing_enabled=payload.briefing_enabled,
            search_enabled=payload.search_enabled,
            memories_enabled=payload.memories_enabled,
            evening_prompt_enabled=payload.evening_prompt_enabled,
        ),
    )
    return _settings_out(item)


@router.get("/diary/entries", response_model=list[DiaryEntryItemResponse])
def list_diary_entries(
    q: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[DiaryEntryItemResponse]:
    items = DiaryService(db_session).list_entries(current_user, query=q, limit=limit)
    return [_entry_out(item) for item in items]


@router.post("/diary/entries", response_model=DiaryEntryItemResponse)
def create_diary_entry(
    payload: DiaryEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiaryEntryItemResponse:
    item = DiaryService(db_session).create_entry(user=current_user, title=payload.title, content=payload.content)
    return _entry_out(item)


@router.post("/diary/entries/audio", response_model=DiaryEntryItemResponse)
async def create_diary_entry_audio(
    title: str = Form(default="Голосовая запись"),
    content: str = Form(default=""),
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiaryEntryItemResponse:
    payload = await audio.read()
    item = DiaryService(db_session).create_entry(
        user=current_user,
        title=title,
        content=content,
        audio_bytes=payload,
        audio_filename=audio.filename or "entry.webm",
    )
    return _entry_out(item)


@router.get("/diary/entries/{entry_id}", response_model=DiaryEntryItemResponse)
def get_diary_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiaryEntryItemResponse:
    try:
        item = DiaryService(db_session).get_entry(current_user, entry_id)
    except DiaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _entry_out(item)


@router.patch("/diary/entries/{entry_id}", response_model=DiaryEntryItemResponse)
def update_diary_entry(
    entry_id: str,
    payload: DiaryEntryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DiaryEntryItemResponse:
    try:
        item = DiaryService(db_session).update_entry(
            current_user,
            entry_id=entry_id,
            title=payload.title,
            content=payload.content,
        )
    except DiaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _entry_out(item)


@router.delete("/diary/entries/{entry_id}")
def delete_diary_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict[str, str]:
    try:
        DiaryService(db_session).delete_entry(current_user, entry_id)
    except DiaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}
