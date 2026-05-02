from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.encrypted_secret_repository import EncryptedSecretRepository
from app.services.secret_crypto_service import SecretCryptoService


class SecretNotFoundError(ValueError):
    pass


class EncryptedSecretService:
    def __init__(self, session: Session, crypto: SecretCryptoService) -> None:
        self._session = session
        self._crypto = crypto
        self._repo = EncryptedSecretRepository(session)

    def set_secret(
        self,
        *,
        user_id: str,
        secret_type: str,
        name: str,
        plaintext_value: str,
    ) -> None:
        encrypted_value = self._crypto.encrypt(plaintext_value)
        self._repo.upsert(
            user_id=user_id,
            secret_type=secret_type,
            name=name,
            encrypted_value=encrypted_value,
        )
        self._session.commit()

    def get_secret(self, *, user_id: str, name: str) -> str:
        stored = self._repo.get_by_user_and_name(user_id=user_id, name=name)
        if stored is None:
            raise SecretNotFoundError("Секрет не найден.")
        return self._crypto.decrypt(stored.encrypted_value)

    def delete_secret(self, *, user_id: str, name: str) -> bool:
        deleted = self._repo.delete_by_user_and_name(user_id=user_id, name=name)
        if deleted:
            self._session.commit()
        return deleted
