from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as _db_models  # noqa: F401
from app.db.base import Base
from app.repositories.encrypted_secret_repository import EncryptedSecretRepository
from app.services.encrypted_secret_service import EncryptedSecretService
from app.services.secret_crypto_service import SecretCryptoService


def _make_session(tmp_path) -> Session:
    db_path = tmp_path / "encrypted-secret-service.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    return session_factory()


def test_secret_is_stored_only_as_ciphertext_and_can_be_decrypted(tmp_path) -> None:
    session = _make_session(tmp_path)
    user_id = "user-123"
    key = Fernet.generate_key().decode("utf-8")

    service = EncryptedSecretService(session, SecretCryptoService(key))
    service.set_secret(
        user_id=user_id,
        secret_type="api_token",
        name="vsellm-token",
        plaintext_value="plain-secret-token",
    )

    repo = EncryptedSecretRepository(session)
    stored = repo.get_by_user_and_name(user_id=user_id, name="vsellm-token")

    assert stored is not None
    assert stored.encrypted_value != b"plain-secret-token"
    assert service.get_secret(user_id=user_id, name="vsellm-token") == "plain-secret-token"
