from __future__ import annotations

from base64 import b64encode

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.common import (
    DocumentTemplateFieldType,
    DocumentTemplateOutputFormat,
    DocumentTemplateProvider,
)
from app.db.models.document_template import DocumentTemplate
from app.db.models.user import User
from app.models.schemas import (
    DocumentTemplateCreateRequest,
    DocumentTemplateFillRequest,
    DocumentTemplateFillResponse,
    DocumentTemplateOutputSettingsSchema,
    DocumentTemplatePatchRequest,
    DocumentTemplateResponse,
    GeneratedDocumentFileSchema,
)
from app.repositories.document_template_repository import DocumentTemplateRepository
from app.services.docx_to_pdf_converter import DocxToPdfConverter
from app.services.document_fill_service import DocumentFillService
from app.storage.runtime import blob_storage

router = APIRouter(tags=["document_templates"])


@router.get("/document-templates", response_model=list[DocumentTemplateResponse])
def list_document_templates(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[DocumentTemplateResponse]:
    repo = DocumentTemplateRepository(db_session)
    return [_to_response(item) for item in repo.list_for_user(current_user.id)]


@router.post("/document-templates", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_document_template(
    payload: DocumentTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DocumentTemplateResponse:
    provider = _parse_provider(payload.provider)
    _validate_fields(payload.fields)
    _validate_output_settings(payload.output_settings)

    item = DocumentTemplate(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description,
        provider=provider,
        file_id=payload.file_id.strip(),
        fields=[field.model_dump() for field in payload.fields],
        output_settings=payload.output_settings.model_dump(),
    )

    repo = DocumentTemplateRepository(db_session)
    repo.create(item)
    db_session.commit()
    db_session.refresh(item)
    return _to_response(item)


@router.patch("/document-templates/{template_id}", response_model=DocumentTemplateResponse)
def patch_document_template(
    template_id: str,
    payload: DocumentTemplatePatchRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DocumentTemplateResponse:
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден.")

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.description is not None:
        item.description = payload.description
    if payload.provider is not None:
        item.provider = _parse_provider(payload.provider)
    if payload.file_id is not None:
        item.file_id = payload.file_id.strip()
    if payload.fields is not None:
        _validate_fields(payload.fields)
        item.fields = [field.model_dump() for field in payload.fields]
    if payload.output_settings is not None:
        _validate_output_settings(payload.output_settings)
        item.output_settings = payload.output_settings.model_dump()

    repo.save(item)
    db_session.commit()
    db_session.refresh(item)
    return _to_response(item)


@router.delete("/document-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Response:
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден.")

    repo.delete(item)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/document-templates/{template_id}/fill", response_model=DocumentTemplateFillResponse)
def fill_document_template(
    template_id: str,
    payload: DocumentTemplateFillRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> DocumentTemplateFillResponse:
    repo = DocumentTemplateRepository(db_session)
    item = repo.get_for_user(template_id, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден.")

    output_settings = item.output_settings
    output_format = DocumentTemplateOutputFormat(output_settings.get("format", "both"))
    output_filename = str(output_settings.get("filename", item.name)).strip() or item.name

    try:
        template_bytes = blob_storage.get_bytes(item.file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Файл шаблона не найден в storage.") from exc

    docx_bytes = DocumentFillService().fill_template(template_bytes=template_bytes, values=payload.values)
    files: list[GeneratedDocumentFileSchema] = []

    if output_format in {DocumentTemplateOutputFormat.DOCX, DocumentTemplateOutputFormat.BOTH}:
        files.append(
            GeneratedDocumentFileSchema(
                filename=f"{output_filename}.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content_base64=b64encode(docx_bytes).decode("ascii"),
            )
        )

    if output_format in {DocumentTemplateOutputFormat.PDF, DocumentTemplateOutputFormat.BOTH}:
        try:
            pdf_bytes = DocxToPdfConverter(get_settings()).convert_to_pdf(docx_bytes)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        files.append(
            GeneratedDocumentFileSchema(
                filename=f"{output_filename}.pdf",
                content_type="application/pdf",
                content_base64=b64encode(pdf_bytes).decode("ascii"),
            )
        )

    return DocumentTemplateFillResponse(files=files)


def _to_response(item: DocumentTemplate) -> DocumentTemplateResponse:
    output_settings = DocumentTemplateOutputSettingsSchema.model_validate(item.output_settings)
    return DocumentTemplateResponse(
        id=item.id,
        user_id=item.user_id,
        name=item.name,
        description=item.description,
        provider=item.provider.value,
        file_id=item.file_id,
        fields=item.fields,
        output_settings=output_settings,
        created_at=item.created_at.isoformat(),
    )


def _parse_provider(raw: str) -> DocumentTemplateProvider:
    try:
        return DocumentTemplateProvider(raw.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неподдерживаемый provider шаблона.") from exc


def _validate_fields(fields) -> None:
    for field in fields:
        try:
            DocumentTemplateFieldType(field.type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип поля: {field.type}") from exc


def _validate_output_settings(settings: DocumentTemplateOutputSettingsSchema) -> None:
    try:
        DocumentTemplateOutputFormat(settings.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неподдерживаемый output format.") from exc
