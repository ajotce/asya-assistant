from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.db.session import create_session
from app.models.schemas import (
    UserDeleteConfirmResponse,
    UserDeleteResponse,
    UserExportStartResponse,
    UserExportStatusResponse,
)
from app.services.user_export import UserExportService

router = APIRouter(prefix="/me", tags=["me"])


def _run_export_in_background(export_id: str) -> None:
    session = create_session()
    try:
        UserExportService(session).run_export(export_id)
    finally:
        session.close()


@router.post("/export", response_model=UserExportStartResponse)
def start_user_export(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserExportStartResponse:
    service = UserExportService(session)
    export_id = service.start_export(current_user.id)
    background_tasks.add_task(_run_export_in_background, export_id)
    return UserExportStartResponse(export_id=export_id, status="pending")


@router.get("/export/{export_id}", response_model=UserExportStatusResponse)
def get_user_export_status(
    export_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserExportStatusResponse:
    try:
        export_status = UserExportService(session).get_status(current_user.id, export_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserExportStatusResponse(
        export_id=export_status.export_id,
        status=export_status.status,
        download_url=export_status.download_url,
        expires_at=export_status.expires_at,
        error=export_status.error,
    )


@router.get("/export/{export_id}/download")
def download_user_export(
    export_id: str,
    token: str = Query(..., min_length=8),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Response:
    # Deprecated compatibility endpoint. New exports should use `download_url` from
    # `GET /api/me/export/{export_id}` (S3 presigned URL with TTL 24h).
    try:
        filename, payload = UserExportService(session).consume_download(current_user.id, export_id, token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/export/{export_id}")
def delete_user_export(
    export_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    try:
        UserExportService(session).delete_export(current_user.id, export_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.delete("", response_model=UserDeleteConfirmResponse | UserDeleteResponse)
def delete_current_user(
    confirmation_token: str | None = Query(default=None),
    password: str | None = Query(default=None, min_length=8),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserDeleteConfirmResponse | UserDeleteResponse:
    service = UserExportService(session)
    if not confirmation_token or not password:
        return UserDeleteConfirmResponse(
            confirmation_token=service.create_delete_confirmation_token(current_user.id),
            expires_in_seconds=900,
        )
    try:
        export_status = service.delete_account(
            user=current_user,
            password=password,
            confirmation_token=confirmation_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserDeleteResponse(
        status="deleted",
        export_id=export_status.export_id,
        export_download_url=export_status.download_url,
    )
