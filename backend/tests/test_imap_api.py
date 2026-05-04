from __future__ import annotations

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.api.deps_auth import get_db_session
from app.main import app
from tests.auth_helpers import override_db_session, setup_test_db


class _FakeImapService:
    def __init__(self, _session) -> None:
        pass

    def test_connection(self, **_kwargs):
        return {"ok": True, "folders": ["INBOX"]}

    def connect(self, **_kwargs):
        return {"ok": True, "folders": ["INBOX"]}

    def list_folders(self, **_kwargs):
        return ["INBOX"]

    def list_messages(self, **_kwargs):
        return [
            SimpleNamespace(
                uid="100",
                subject="Hi",
                from_name="Sender",
                from_email="sender@example.com",
                date="Mon, 01 Jan 2026 10:00:00 +0000",
                is_unread=True,
            )
        ]

    def get_message(self, **_kwargs):
        return SimpleNamespace(
            uid="100",
            subject="Hi",
            from_name="Sender",
            from_email="sender@example.com",
            date="Mon, 01 Jan 2026 10:00:00 +0000",
            is_unread=True,
            to=["you@example.com"],
            cc=[],
            text_body="body",
        )

    def search_messages(self, **_kwargs):
        return self.list_messages()

    def mark_as_read(self, **_kwargs):
        return None

    def disconnect(self, **_kwargs):
        return None


def _register_and_login(client: TestClient, email: str) -> None:
    register = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "User", "password": "strong-pass-123"},
    )
    assert register.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def test_imap_endpoints_basic_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    monkeypatch.setattr("app.api.routes_integrations.ImapService", _FakeImapService)

    client = TestClient(app)
    _register_and_login(client, "imap-api@example.com")

    payload = {
        "email": "imap-api@example.com",
        "username": "imap-api@example.com",
        "password": "secret",
        "host": "imap.example.com",
        "port": 993,
        "security": "ssl",
    }

    tested = client.post("/api/integrations/imap/test", json=payload)
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    connected = client.post("/api/integrations/imap/connect", json=payload)
    assert connected.status_code == 200

    folders = client.get("/api/integrations/imap/folders")
    assert folders.status_code == 200
    assert folders.json()["folders"] == ["INBOX"]

    listed = client.get("/api/integrations/imap/messages?folder=INBOX&limit=10")
    assert listed.status_code == 200
    assert listed.json()[0]["uid"] == "100"

    read = client.get("/api/integrations/imap/messages/100?folder=INBOX")
    assert read.status_code == 200
    assert read.json()["text_body"] == "body"

    searched = client.get("/api/integrations/imap/search?q=invoice&folder=INBOX")
    assert searched.status_code == 200
    assert searched.json()[0]["from_email"] == "sender@example.com"

    marked = client.post("/api/integrations/imap/messages/100/read?folder=INBOX")
    assert marked.status_code == 200

    disconnected = client.delete("/api/integrations/imap")
    assert disconnected.status_code == 200

    app.dependency_overrides.clear()
