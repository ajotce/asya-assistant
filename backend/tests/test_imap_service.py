from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider, UserStatus
from app.db.models.user import User
from app.integrations.imap import ImapService, ImapSettings
from app.services.integration_connection_service import IntegrationConnectionService
from tests.auth_helpers import setup_test_db


class _FakeImapClient:
    def __init__(self, *_args, **_kwargs) -> None:
        self._selected = None

    def starttls(self) -> None:
        return None

    def login(self, *_args) -> tuple[str, list[bytes]]:
        return "OK", [b"logged"]

    def logout(self) -> tuple[str, list[bytes]]:
        return "OK", [b"bye"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"']

    def select(self, folder: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        _ = readonly
        self._selected = folder
        return "OK", [b"1"]

    def uid(self, command: str, *args):
        if command == "search":
            return "OK", [b"10 20"]
        if command == "fetch":
            uid = args[0]
            if uid == "20":
                header = b"Subject: Hello\r\nFrom: Test <test@example.com>\r\nDate: Mon, 01 Jan 2026 10:00:00 +0000\r\n\r\n"
                return "OK", [(b'20 (FLAGS (\\Seen) BODY[HEADER] {100}', header), b')']
            body = (
                b"Subject: Hello\r\n"
                b"From: Test <test@example.com>\r\n"
                b"To: user@example.com\r\n"
                b"Date: Mon, 01 Jan 2026 10:00:00 +0000\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                b"Body"
            )
            return "OK", [(b'10 (FLAGS () RFC822 {120}', body), b')']
        if command == "store":
            return "OK", [b"stored"]
        return "NO", [b"unsupported"]


def _create_user(session: Session) -> User:
    user = User(email="imap-service@example.com", display_name="imap", role="user", status=UserStatus.ACTIVE, password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_imap_service_connect_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    _, engine = setup_test_db(tmp_path, monkeypatch)
    monkeypatch.setattr("imaplib.IMAP4_SSL", _FakeImapClient)
    monkeypatch.setattr("imaplib.IMAP4", _FakeImapClient)

    with Session(bind=engine) as session:
        user = _create_user(session)
        service = ImapService(session)
        service.connect(
            user=user,
            settings=ImapSettings(
                email="imap-user@example.com",
                username="imap-user@example.com",
                password="secret-pass",
                host="imap.example.com",
                port=993,
                security="ssl",
            ),
        )

        listed = service.list_messages(user_id=user.id, folder="INBOX", limit=10)
        assert len(listed) == 2
        assert listed[0].uid == "20"

        message = service.get_message(user_id=user.id, uid="10", folder="INBOX")
        assert message.text_body == "Body"
        assert message.from_email == "test@example.com"

        service.mark_as_read(user_id=user.id, uid="10", folder="INBOX")

        conn = IntegrationConnectionService(session).get_connection(user=user, provider=IntegrationProvider.IMAP)
        assert conn.status == IntegrationConnectionStatus.CONNECTED
