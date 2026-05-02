from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.encrypted_secret import EncryptedSecret


class EncryptedSecretRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        user_id: str,
        secret_type: str,
        name: str,
        encrypted_value: bytes,
    ) -> EncryptedSecret:
        existing = self.get_by_user_and_name(user_id=user_id, name=name)
        if existing is None:
            existing = EncryptedSecret(
                user_id=user_id,
                secret_type=secret_type,
                name=name,
                encrypted_value=encrypted_value,
            )
            self._session.add(existing)
        else:
            existing.secret_type = secret_type
            existing.encrypted_value = encrypted_value
            self._session.add(existing)

        self._session.flush()
        return existing

    def get_by_user_and_name(self, *, user_id: str, name: str) -> EncryptedSecret | None:
        stmt = select(EncryptedSecret).where(
            EncryptedSecret.user_id == user_id,
            EncryptedSecret.name == name,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def delete_by_user_and_name(self, *, user_id: str, name: str) -> bool:
        item = self.get_by_user_and_name(user_id=user_id, name=name)
        if item is None:
            return False
        self._session.delete(item)
        self._session.flush()
        return True
