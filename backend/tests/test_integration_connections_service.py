from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider, UserStatus
from app.repositories.encrypted_secret_repository import EncryptedSecretRepository
from app.repositories.user_repository import UserRepository
from app.services.integration_connection_service import (
    IntegrationConnectionService,
    IntegrationConnectionUpsertPayload,
)
from tests.auth_helpers import setup_test_db


def _create_user(session: Session, *, email: str, display_name: str):
    user = UserRepository(session).create(
        email=email,
        display_name=display_name,
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return user


def test_connections_are_user_scoped_and_tokens_are_encrypted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)

    with Session(bind=engine) as session:
        user_a = _create_user(session, email="integration-a@example.com", display_name="A")
        user_b = _create_user(session, email="integration-b@example.com", display_name="B")

        service = IntegrationConnectionService(session)
        service.upsert_connection(
            user=user_a,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.LINEAR,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["issues:read", "issues:write"],
                access_token="a-access-token",
                refresh_token="a-refresh-token",
            ),
        )

        listed_a = service.list_connections(user=user_a)
        listed_b = service.list_connections(user=user_b)
        assert len(listed_a) == 1
        assert listed_a[0].provider == IntegrationProvider.LINEAR
        assert listed_a[0].status == IntegrationConnectionStatus.CONNECTED
        assert listed_b == []

        secret_repo = EncryptedSecretRepository(session)
        stored_access = secret_repo.get_by_user_and_name(
            user_id=user_a.id,
            name="integration:linear:access_token",
        )
        stored_refresh = secret_repo.get_by_user_and_name(
            user_id=user_a.id,
            name="integration:linear:refresh_token",
        )
        assert stored_access is not None
        assert stored_refresh is not None
        assert stored_access.encrypted_value != b"a-access-token"
        assert stored_refresh.encrypted_value != b"a-refresh-token"


def test_disconnect_revokes_connection_and_deletes_only_current_user_secrets(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)

    with Session(bind=engine) as session:
        user_a = _create_user(session, email="disconnect-a@example.com", display_name="A")
        user_b = _create_user(session, email="disconnect-b@example.com", display_name="B")
        service = IntegrationConnectionService(session)

        service.upsert_connection(
            user=user_a,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.TODOIST,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["tasks:read"],
                access_token="a-token",
                refresh_token="a-refresh",
            ),
        )
        service.upsert_connection(
            user=user_b,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.TODOIST,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["tasks:read"],
                access_token="b-token",
                refresh_token="b-refresh",
            ),
        )

        disconnected = service.disconnect(user=user_a, provider=IntegrationProvider.TODOIST)
        assert disconnected.status == IntegrationConnectionStatus.REVOKED

        secret_repo = EncryptedSecretRepository(session)
        assert secret_repo.get_by_user_and_name(
            user_id=user_a.id,
            name="integration:todoist:access_token",
        ) is None
        assert secret_repo.get_by_user_and_name(
            user_id=user_a.id,
            name="integration:todoist:refresh_token",
        ) is None
        assert secret_repo.get_by_user_and_name(
            user_id=user_b.id,
            name="integration:todoist:access_token",
        ) is not None
