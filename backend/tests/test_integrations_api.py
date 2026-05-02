from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.integration_connection_service import (
    IntegrationConnectionService,
    IntegrationConnectionUpsertPayload,
)
from tests.auth_helpers import override_db_session, setup_test_db


def _register_and_login(client: TestClient, *, email: str, display_name: str) -> None:
    register = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": display_name, "password": "strong-pass-123"},
    )
    assert register.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def _upsert_connection_for_user(engine, email: str) -> None:
    with Session(bind=engine) as session:
        user = UserRepository(session).get_by_email(email)
        assert user is not None
        IntegrationConnectionService(session).upsert_connection(
            user=user,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.LINEAR,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["issues:read"],
                access_token="user-access-token",
                refresh_token="user-refresh-token",
            ),
        )


def test_integrations_are_user_scoped_and_do_not_expose_tokens(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, email="int-a@example.com", display_name="A")
    _register_and_login(client_b, email="int-b@example.com", display_name="B")
    _upsert_connection_for_user(engine, "int-a@example.com")

    list_a = client_a.get("/api/integrations")
    assert list_a.status_code == 200
    linear_a = next(item for item in list_a.json() if item["provider"] == "linear")
    assert linear_a["status"] == "connected"
    assert "access_token" not in linear_a
    assert "refresh_token" not in linear_a

    get_b = client_b.get("/api/integrations/linear")
    assert get_b.status_code == 200
    assert get_b.json()["status"] == "not_connected"
    app.dependency_overrides.clear()


def test_disconnect_changes_status_for_current_user_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, email="disc-a@example.com", display_name="A")
    _register_and_login(client_b, email="disc-b@example.com", display_name="B")
    _upsert_connection_for_user(engine, "disc-a@example.com")
    _upsert_connection_for_user(engine, "disc-b@example.com")

    disconnect = client_a.delete("/api/integrations/linear")
    assert disconnect.status_code == 200
    assert disconnect.json()["status"] == "revoked"

    a_state = client_a.get("/api/integrations/linear")
    b_state = client_b.get("/api/integrations/linear")
    assert a_state.status_code == 200
    assert b_state.status_code == 200
    assert a_state.json()["status"] == "revoked"
    assert b_state.json()["status"] == "connected"
    app.dependency_overrides.clear()
