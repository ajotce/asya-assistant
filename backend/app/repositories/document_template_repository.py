from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document_template import DocumentTemplate


class DocumentTemplateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, *, user_id: str) -> list[DocumentTemplate]:
        stmt = (
            select(DocumentTemplate)
            .where(DocumentTemplate.user_id == user_id)
            .order_by(DocumentTemplate.created_at.desc())
        )
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, *, template_id: str, user_id: str) -> DocumentTemplate | None:
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.user_id == user_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: str,
        name: str,
        description: str | None,
        provider: str,
        file_id: str,
        fields: list[dict],
        output_settings: dict,
    ) -> DocumentTemplate:
        item = DocumentTemplate(
            user_id=user_id,
            name=name,
            description=description,
            provider=provider,
            file_id=file_id,
            fields=fields,
            output_settings=output_settings,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def update(
        self,
        *,
        item: DocumentTemplate,
        name: str,
        description: str | None,
        provider: str,
        file_id: str,
        fields: list[dict],
        output_settings: dict,
    ) -> DocumentTemplate:
        item.name = name
        item.description = description
        item.provider = provider
        item.file_id = file_id
        item.fields = fields
        item.output_settings = output_settings
        self._session.flush()
        return item

    def delete(self, *, item: DocumentTemplate) -> None:
        self._session.delete(item)
        self._session.flush()
