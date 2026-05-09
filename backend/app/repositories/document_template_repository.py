from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document_template import DocumentTemplate


class DocumentTemplateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str) -> list[DocumentTemplate]:
        stmt = (
            select(DocumentTemplate)
            .where(DocumentTemplate.user_id == user_id)
            .order_by(DocumentTemplate.created_at.desc())
        )
        return list(self._session.execute(stmt).scalars())

    def get_for_user(self, template_id: str, user_id: str) -> DocumentTemplate | None:
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.id == template_id,
            DocumentTemplate.user_id == user_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(self, template: DocumentTemplate) -> DocumentTemplate:
        self._session.add(template)
        self._session.flush()
        return template

    def save(self, template: DocumentTemplate) -> DocumentTemplate:
        self._session.add(template)
        self._session.flush()
        return template

    def delete(self, template: DocumentTemplate) -> None:
        self._session.delete(template)
        self._session.flush()
