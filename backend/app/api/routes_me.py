from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.models.schemas import (
    DeleteMeConfirmResponse,
    DeleteMePrepareResponse,
    DeleteMeRequest,
    UserExportStartResponse,
    UserExportStatusResponse,
)
from app.services.user_export import UserExportError, UserExportService

router = APIRouter(tags=["me"])


@router.post("/me/export", response_model=UserExportStartResponse)
def start_export(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> UserExportStartResponse:
    service = UserExportService(db_session)
    export_id = service.start_export(current_user.id)
    return UserExportStartResponse(export_id=export_id, status="pending")


@router.get("/me/export/{export_id}", response_model=UserExportStatusResponse)
def get_export_status(
    export_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> UserExportStatusResponse:
    service = UserExportService(db_session)
    try:
        export = service.get_status(export_id, current_user.id)
    except UserExportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    download_url = None
    expires_at = None
    if export.status.value == "ready":
        token, token_expires = service.get_download_url(export_id, current_user.id)
        download_url = f"/api/me/export/download/{token}"
        expires_at = token_expires.isoformat()

    return UserExportStatusResponse(
        export_id=export.id,
        status=export.status.value,
        download_url=download_url,
        expires_at=expires_at,
    )


@router.get("/me/export/download/{token}")
def download_export(token: str, db_session: Session = Depends(get_db_session)) -> FileResponse:
    service = UserExportService(db_session)
    try:
        file_path = service.consume_download_token(token)
    except UserExportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(path=file_path, filename="asya-user-export.zip", media_type="application/zip")


@router.delete("/me", response_model=DeleteMePrepareResponse)
def prepare_delete_me(
    payload: DeleteMeRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DeleteMePrepareResponse:
    service = UserExportService(db_session)
    try:
        confirmation_token, expires_at = service.prepare_delete_confirmation(current_user, payload.password)
    except UserExportError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return DeleteMePrepareResponse(confirmation_token=confirmation_token, expires_at=expires_at.isoformat())


@router.delete("/me/confirm", response_model=DeleteMeConfirmResponse)
def confirm_delete_me(
    token: str = Query(..., min_length=16),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DeleteMeConfirmResponse:
    service = UserExportService(db_session)
    try:
        export_id, download_token, expires_at = service.delete_user(current_user, token)
    except UserExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    download_url = f"/api/me/export/download/{download_token}" if download_token else None
    return DeleteMeConfirmResponse(
        status="deleted",
        export_id=export_id,
        download_url=download_url,
        expires_at=expires_at.isoformat() if expires_at else None,
    )
