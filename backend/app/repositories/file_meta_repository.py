from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.file_meta import FileMeta


class FileMetaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        file_id: str,
        user_id: str,
        chat_id: str | None,
        filename: str,
        content_type: str,
        size: int,
        storage_path: str,
        extracted_text_status: str | None,
        extracted_text_meta: dict[str, Any] | None,
    ) -> FileMeta:
        item = FileMeta(
            id=file_id,
            user_id=user_id,
            chat_id=chat_id,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_path=storage_path,
            extracted_text_status=extracted_text_status,
            extracted_text_meta=extracted_text_meta,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def list_for_chat_user(self, *, chat_id: str, user_id: str) -> list[FileMeta]:
        stmt = (
            select(FileMeta)
            .where(FileMeta.chat_id == chat_id, FileMeta.user_id == user_id)
            .order_by(FileMeta.created_at.asc())
        )
        return list(self._session.execute(stmt).scalars())

    def get_for_chat_user(self, *, file_id: str, chat_id: str, user_id: str) -> FileMeta | None:
        stmt = select(FileMeta).where(
            FileMeta.id == file_id,
            FileMeta.chat_id == chat_id,
            FileMeta.user_id == user_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def delete_for_chat_user(self, *, chat_id: str, user_id: str) -> int:
        stmt = delete(FileMeta).where(FileMeta.chat_id == chat_id, FileMeta.user_id == user_id)
        result = self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)
