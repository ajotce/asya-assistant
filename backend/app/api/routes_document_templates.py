from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.user import User
from app.integrations.file_storage import FileStorageError
from app.models.schemas import (
    DocumentTemplateCreateRequest,
    DocumentTemplateFillPreviewResponse,
    DocumentTemplateFillRequest,
    DocumentTemplateItemResponse,
    DocumentTemplateUpdateRequest,
)
from app.repositories.document_template_repository import DocumentTemplateRepository
from app.services.document_fill_service import DocumentFillService, DocumentFillValidationError
from app.services.file_storage_service import FileStorageProviderNotSupportedError, FileStorageService

router = APIRouter(tags=["document-templates"])


def _to_response(item) -> DocumentTemplateItemResponse:
    return DocumentTemplateItemResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        provider=item.provider,
        file_id=item.file_id,
        fields=item.fields or [],
        output_settings=item.output_settings or {},
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/document-templates", response_model=list[DocumentTemplateItemResponse])
def list_document_templates(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[DocumentTemplateItemResponse]:
    repo = DocumentTemplateRepository(db_session)
    items = repo.list_for_user(user_id=current_user.id)
    return [_to_response(item) for item in items]


@router.post(
    "/document-templates",
    response_model=DocumentTemplateItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_template(
    payload: DocumentTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DocumentTemplateItemResponse:
    repo = DocumentTemplateRepository(db_session)
    item = repo.create(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description,
        provider=payload.provider.strip(),
        file_id=payload.file_id.strip(),
        fields=[item.model_dump() for item in payload.fields],
        output_settings=payload.output_settings,
    )
    return _to_response(item)


@router.patch("/document-templates/{template_id}", response_model=DocumentTemplateItemResponse)
def update_document_template(
    template_id: str,
    payload: DocumentTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DocumentTemplateItemResponse:
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id=template_id, user_id=current_user.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден.")
    updated = repo.update(
        item=item,
        name=payload.name.strip(),
        description=payload.description,
        provider=payload.provider.strip(),
        file_id=payload.file_id.strip(),
        fields=[field.model_dump() for field in payload.fields],
        output_settings=payload.output_settings,
    )
    return _to_response(updated)


@router.delete("/document-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> None:
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id=template_id, user_id=current_user.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден.")
    repo.delete(item=item)


@router.post("/document-templates/{template_id}/fill")
def fill_document_template(
    template_id: str,
    payload: DocumentTemplateFillRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
):
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id=template_id, user_id=current_user.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден.")

    storage = FileStorageService(db_session, user_id=current_user.id)
    try:
        template_bytes = storage.read(provider=item.provider, item_id=item.file_id)
    except FileStorageProviderNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filler = DocumentFillService()
    preview = filler.preview(
        template_fields=item.fields or [],
        values=payload.values,
        template_bytes=template_bytes,
    )
    if payload.preview_only:
        return DocumentTemplateFillPreviewResponse(
            missing_fields=preview.missing_fields,
            invalid_fields=preview.invalid_fields,
            ready=preview.ok,
        )

    if not preview.ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "missing_fields": preview.missing_fields,
                "invalid_fields": preview.invalid_fields,
            },
        )

    output_name = str((item.output_settings or {}).get("filename") or item.name or "filled_template")
    try:
        artifact = filler.fill(
            template_fields=item.fields or [],
            values=payload.values,
            template_bytes=template_bytes,
            output_filename=output_name,
            user_id=current_user.id,
        )
    except DocumentFillValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return FileResponse(
        artifact.path,
        media_type=artifact.content_type,
        filename=artifact.filename,
    )
