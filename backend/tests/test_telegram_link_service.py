from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.models.user import User
from app.db.session import get_engine
from app.integrations.telegram.link_service import (
    TelegramLinkError,
    TelegramLinkService,
)
from app.repositories.telegram_link_token_repository import TelegramLinkTokenRepository


@pytest.fixture
def test_session(tmp_path, monkeypatch):
    db_path = tmp_path / "telegram-test.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "asya_test_bot")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    yield session
    session.close()
    get_settings.cache_clear()
    get_engine.cache_clear()


def _create_user(session: Session, email: str) -> User:
    user = User(email=email, display_name="Test", role="user", status="active")
    session.add(user)
    session.flush()
    return user


def test_link_token_flow(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session, "test@example.com")
    service = TelegramLinkService(session, settings)

    result = service.create_one_time_token(user=user)
    assert result.one_time_token
    assert "?start=" in result.bot_start_url
    assert result.expires_at > datetime.now(timezone.utc)

    status = service.status(user=user)
    assert status.is_linked is False

    link = service.consume_start_token(
        token=result.one_time_token,
        telegram_user_id="111",
        telegram_chat_id="222",
        telegram_username="testuser",
    )
    assert link.user_id == user.id
    assert link.telegram_user_id == "111"

    status = service.status(user=user)
    assert status.is_linked is True
    assert status.telegram_user_id == "111"

    conn = IntegrationConnectionStatus
    prov = IntegrationProvider
    from app.services.integration_connection_service import IntegrationConnectionService
    int_svc = IntegrationConnectionService(session)
    int_conn = int_svc.get_connection_or_default(user=user, provider=prov.TELEGRAM)
    assert int_conn.status == conn.CONNECTED


def test_unlink(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session, "unlink@example.com")
    service = TelegramLinkService(session, settings)

    token = service.create_one_time_token(user=user)
    service.consume_start_token(
        token=token.one_time_token,
        telegram_user_id="333",
        telegram_chat_id="444",
        telegram_username=None,
    )

    assert service.status(user=user).is_linked is True
    unlinked = service.unlink(user=user)
    assert unlinked is True
    assert service.status(user=user).is_linked is False


def test_invalid_token(test_session):
    session = test_session
    settings = get_settings()
    service = TelegramLinkService(session, settings)
    with pytest.raises(TelegramLinkError):
        service.consume_start_token(
            token="invalid",
            telegram_user_id="1",
            telegram_chat_id="2",
            telegram_username=None,
        )


def test_token_pruning(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session, "prune@example.com")
    service = TelegramLinkService(session, settings)

    result = service.create_one_time_token(user=user)
    repo = TelegramLinkTokenRepository(session)

    token_row = repo.get_valid_by_hash(TelegramLinkService._hash(result.one_time_token))
    assert token_row is not None

    token_row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.flush()

    pruned = repo.prune_expired()
    assert pruned >= 1

    assert repo.get_valid_by_hash(TelegramLinkService._hash(result.one_time_token)) is None


def test_deactivate_previous_link(test_session):
    session = test_session
    settings = get_settings()
    user = _create_user(session, "relink@example.com")
    service = TelegramLinkService(session, settings)

    token1 = service.create_one_time_token(user=user)
    link1 = service.consume_start_token(
        token=token1.one_time_token,
        telegram_user_id="555",
        telegram_chat_id="666",
        telegram_username=None,
    )
    assert link1.is_active

    token2 = service.create_one_time_token(user=user)
    link2 = service.consume_start_token(
        token=token2.one_time_token,
        telegram_user_id="777",
        telegram_chat_id="888",
        telegram_username=None,
    )
    assert link2.is_active

    session.refresh(link1)
    assert link1.is_active is False
