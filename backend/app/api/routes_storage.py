from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.integrations.file_storage import FileStorageError, FileStorageFile, FileStorageFolder
from app.models.schemas import StorageItemResponse, StorageProviderInfoResponse
from app.services.file_storage_service import FileStorageProviderNotSupportedError, FileStorageService
from app.services.settings_service import SettingsService
from app.core.config import get_settings

router = APIRouter(tags=["storage"])


def _item_to_response(item: FileStorageFile | FileStorageFolder) -> StorageItemResponse:
    return StorageItemResponse(
        provider=item.provider or "",
        id=item.id,
        name=item.name,
        path=item.path,
        kind="folder" if isinstance(item, FileStorageFolder) else "file",
        size_bytes=None if isinstance(item, FileStorageFolder) else item.size_bytes,
        mime_type=None if isinstance(item, FileStorageFolder) else item.mime_type,
        modified_at=item.modified_at.isoformat() if item.modified_at else None,
    )


def _resolve_provider(raw: str | None, *, settings_service: SettingsService, user_id: str) -> str:
    if raw and raw.strip():
        return raw.strip()
    return settings_service.get_settings(user_id=user_id).default_storage_provider


@router.get("/storage/providers", response_model=list[StorageProviderInfoResponse])
def list_storage_providers(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[StorageProviderInfoResponse]:
    service = FileStorageService(db_session, user_id=current_user.id)
    return [StorageProviderInfoResponse(**item.__dict__) for item in service.list_providers()]


@router.get("/storage/files", response_model=list[StorageItemResponse])
def list_storage_files(
    provider: str | None = Query(default=None),
    path: str = Query(default=""),
    search: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[StorageItemResponse]:
    settings_service = SettingsService(get_settings(), db_session=db_session)
    resolved = _resolve_provider(provider, settings_service=settings_service, user_id=current_user.id)
    service = FileStorageService(db_session, user_id=current_user.id)
    try:
        if search and search.strip():
            items = service.search(provider=resolved, query=search.strip(), path=path or None)
        else:
            items = service.list(provider=resolved, path=path)
    except FileStorageProviderNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_item_to_response(item) for item in items]


@router.post("/storage/files", response_model=StorageItemResponse)
def upload_storage_file(
    provider: str | None = Query(default=None),
    path: str = Query(..., min_length=1),
    overwrite: bool = Query(default=True),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> StorageItemResponse:
    settings_service = SettingsService(get_settings(), db_session=db_session)
    resolved = _resolve_provider(provider, settings_service=settings_service, user_id=current_user.id)
    content = file.file.read()
    service = FileStorageService(db_session, user_id=current_user.id)
    try:
        item = service.write(provider=resolved, path=path, content=content, overwrite=overwrite)
    except FileStorageProviderNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _item_to_response(item)


@router.get("/storage/files/{provider}/{item_id}", response_model=StorageItemResponse)
def get_storage_file(
    provider: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> StorageItemResponse:
    service = FileStorageService(db_session, user_id=current_user.id)
    try:
        item = service.get_metadata(provider=provider, item_id=item_id)
    except FileStorageProviderNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _item_to_response(item)
