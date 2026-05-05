from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
import imaplib
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.models.user import User
from app.services.encrypted_secret_service import EncryptedSecretService, SecretNotFoundError
from app.services.integration_connection_service import IntegrationConnectionService, IntegrationConnectionUpsertPayload
from app.services.secret_crypto_service import SecretCryptoService


class ImapConfigurationError(ValueError):
    pass


class ImapConnectionError(RuntimeError):
    pass


class ImapMessageNotFoundError(ValueError):
    pass


@dataclass
class ImapSettings:
    email: str
    username: str
    password: str
    host: str
    port: int
    security: str


@dataclass
class ImapMessageSummary:
    uid: str
    subject: str
    from_name: str
    from_email: str
    date: str | None
    is_unread: bool


@dataclass
class ImapMessageDetails(ImapMessageSummary):
    to: list[str]
    cc: list[str]
    text_body: str


class ImapService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings()
        self._secret_service = EncryptedSecretService(
            session,
            SecretCryptoService(self._settings.master_encryption_key),
        )
        self._connections = IntegrationConnectionService(session)

    def test_connection(self, *, settings: ImapSettings) -> dict:
        with self._imap_client(settings) as client:
            status, mailboxes = client.list()
            if status != "OK":
                raise ImapConnectionError("IMAP сервер не вернул список папок.")
            folders = [self._parse_folder_name(line) for line in (mailboxes or [])]
        return {"ok": True, "folders": folders}

    def connect(self, *, user: User, settings: ImapSettings) -> dict:
        tested = self.test_connection(settings=settings)
        self._store_settings(user_id=user.id, settings=settings)
        self._connections.upsert_connection(
            user=user,
            payload=IntegrationConnectionUpsertPayload(
                provider=IntegrationProvider.IMAP,
                status=IntegrationConnectionStatus.CONNECTED,
                scopes=["mail.read", "mail.mark_read"],
                connected_at=datetime.now(timezone.utc),
                safe_error_metadata=None,
            ),
        )
        return tested

    def list_folders(self, *, user_id: str) -> list[str]:
        settings = self._load_settings(user_id=user_id)
        with self._imap_client(settings) as client:
            status, mailboxes = client.list()
            if status != "OK":
                raise ImapConnectionError("Не удалось получить список папок.")
            self._mark_synced(user_id)
            return [self._parse_folder_name(line) for line in (mailboxes or [])]

    def list_messages(self, *, user_id: str, folder: str = "INBOX", limit: int = 30) -> list[ImapMessageSummary]:
        settings = self._load_settings(user_id=user_id)
        with self._imap_client(settings) as client:
            self._select_folder(client=client, folder=folder)
            status, data = client.uid("search", None, "ALL")
            if status != "OK":
                raise ImapConnectionError("Не удалось получить список писем.")
            uids = (data[0] or b"").decode("utf-8").split()
            chosen = list(reversed(uids))[: max(1, min(limit, 200))]
            result: list[ImapMessageSummary] = []
            for uid in chosen:
                fetched = self._fetch_headers(client=client, uid=uid)
                if fetched is not None:
                    result.append(fetched)
            self._mark_synced(user_id)
            return result

    def get_message(self, *, user_id: str, uid: str, folder: str = "INBOX") -> ImapMessageDetails:
        settings = self._load_settings(user_id=user_id)
        with self._imap_client(settings) as client:
            self._select_folder(client=client, folder=folder)
            status, data = client.uid("fetch", uid, "(RFC822 FLAGS)")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                raise ImapMessageNotFoundError("Письмо не найдено.")
            raw_message = data[0][1]
            if not isinstance(raw_message, bytes):
                raise ImapMessageNotFoundError("Письмо не найдено.")
            parsed = message_from_bytes(raw_message)
            flags = self._extract_flags(data)
            self._mark_synced(user_id)
            return ImapMessageDetails(
                uid=uid,
                subject=self._decode_header(parsed.get("Subject")),
                from_name=self._extract_from_name(parsed.get("From")),
                from_email=self._extract_from_email(parsed.get("From")),
                date=parsed.get("Date"),
                is_unread="\\Seen" not in flags,
                to=self._split_addresses(parsed.get("To")),
                cc=self._split_addresses(parsed.get("Cc")),
                text_body=self._extract_text_body(parsed),
            )

    def search_messages(self, *, user_id: str, query: str, folder: str = "INBOX", limit: int = 30) -> list[ImapMessageSummary]:
        if not query.strip():
            return []
        settings = self._load_settings(user_id=user_id)
        with self._imap_client(settings) as client:
            self._select_folder(client=client, folder=folder)
            escaped = query.replace('"', "")
            status, data = client.uid("search", None, "TEXT", f'"{escaped}"')
            if status != "OK":
                raise ImapConnectionError("Поиск писем завершился ошибкой.")
            uids = (data[0] or b"").decode("utf-8").split()
            chosen = list(reversed(uids))[: max(1, min(limit, 200))]
            result: list[ImapMessageSummary] = []
            for uid in chosen:
                fetched = self._fetch_headers(client=client, uid=uid)
                if fetched is not None:
                    result.append(fetched)
            self._mark_synced(user_id)
            return result

    def mark_as_read(self, *, user_id: str, uid: str, folder: str = "INBOX") -> None:
        settings = self._load_settings(user_id=user_id)
        with self._imap_client(settings) as client:
            self._select_folder(client=client, folder=folder)
            status, _ = client.uid("store", uid, "+FLAGS", "(\\Seen)")
            if status != "OK":
                raise ImapConnectionError("Не удалось отметить письмо как прочитанное.")
            self._mark_synced(user_id)

    def disconnect(self, *, user: User) -> None:
        self._connections.disconnect(user=user, provider=IntegrationProvider.IMAP)
        for suffix in ["email", "username", "password", "host", "port", "security"]:
            self._secret_service.delete_secret(user_id=user.id, name=self._secret_name(suffix))

    def _store_settings(self, *, user_id: str, settings: ImapSettings) -> None:
        if settings.security not in {"ssl", "starttls", "plain"}:
            raise ImapConfigurationError("Неподдерживаемый режим security. Используйте ssl/starttls/plain.")
        for key, value in {
            "email": settings.email,
            "username": settings.username,
            "password": settings.password,
            "host": settings.host,
            "port": str(settings.port),
            "security": settings.security,
        }.items():
            self._secret_service.set_secret(
                user_id=user_id,
                secret_type="integration_secret",
                name=self._secret_name(key),
                plaintext_value=value,
            )

    def _load_settings(self, *, user_id: str) -> ImapSettings:
        try:
            return ImapSettings(
                email=self._secret_service.get_secret(user_id=user_id, name=self._secret_name("email")),
                username=self._secret_service.get_secret(user_id=user_id, name=self._secret_name("username")),
                password=self._secret_service.get_secret(user_id=user_id, name=self._secret_name("password")),
                host=self._secret_service.get_secret(user_id=user_id, name=self._secret_name("host")),
                port=int(self._secret_service.get_secret(user_id=user_id, name=self._secret_name("port"))),
                security=self._secret_service.get_secret(user_id=user_id, name=self._secret_name("security")),
            )
        except SecretNotFoundError as exc:
            raise ImapConfigurationError("IMAP аккаунт не подключен.") from exc
        except ValueError as exc:
            raise ImapConfigurationError("Некорректная конфигурация IMAP аккаунта.") from exc

    @contextmanager
    def _imap_client(self, settings: ImapSettings):
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        try:
            if settings.security == "ssl":
                client = imaplib.IMAP4_SSL(settings.host, settings.port)
            else:
                client = imaplib.IMAP4(settings.host, settings.port)
                if settings.security == "starttls":
                    client.starttls()
            client.login(settings.username, settings.password)
            yield client
        except (imaplib.IMAP4.error, OSError) as exc:
            raise ImapConnectionError("Не удалось подключиться к IMAP серверу. Проверьте host/port/login/password.") from exc
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:  # noqa: BLE001
                    pass

    @staticmethod
    def _secret_name(suffix: str) -> str:
        return f"integration:{IntegrationProvider.IMAP.value}:{suffix}"

    @staticmethod
    def _parse_folder_name(line: bytes) -> str:
        try:
            text = line.decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            return ""
        parts = text.split(' "/" ')
        if len(parts) >= 2:
            return parts[-1].strip('"')
        return text.strip()

    def _fetch_headers(self, *, client: imaplib.IMAP4, uid: str) -> ImapMessageSummary | None:
        status, data = client.uid("fetch", uid, "(BODY.PEEK[HEADER] FLAGS)")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            return None
        msg = message_from_bytes(data[0][1])
        flags = self._extract_flags(data)
        return ImapMessageSummary(
            uid=uid,
            subject=self._decode_header(msg.get("Subject")),
            from_name=self._extract_from_name(msg.get("From")),
            from_email=self._extract_from_email(msg.get("From")),
            date=msg.get("Date"),
            is_unread="\\Seen" not in flags,
        )

    @staticmethod
    def _select_folder(*, client: imaplib.IMAP4, folder: str) -> None:
        status, _ = client.select(folder, readonly=False)
        if status != "OK":
            raise ImapConnectionError(f"Не удалось открыть папку '{folder}'.")

    @staticmethod
    def _extract_flags(data: list) -> set[str]:
        flags_text = ""
        for item in data:
            if isinstance(item, tuple) and isinstance(item[0], bytes):
                flags_text += item[0].decode("utf-8", errors="ignore")
        found = re.findall(r"FLAGS \\(([^)]*)\\)", flags_text)
        if not found:
            return set()
        raw = found[-1].strip()
        if not raw:
            return set()
        return set(raw.split())

    @staticmethod
    def _decode_header(raw: str | None) -> str:
        if not raw:
            return ""
        chunks = decode_header(raw)
        parts: list[str] = []
        for value, charset in chunks:
            if isinstance(value, bytes):
                parts.append(value.decode(charset or "utf-8", errors="replace"))
            elif isinstance(value, str):
                parts.append(value)
            else:
                parts.append(str(value))
        return "".join(parts).strip()

    @staticmethod
    def _extract_from_email(raw: str | None) -> str:
        if not raw:
            return ""
        match = re.search(r"<([^>]+)>", raw)
        return (match.group(1) if match else raw).strip().lower()

    @staticmethod
    def _extract_from_name(raw: str | None) -> str:
        if not raw:
            return ""
        cleaned = re.sub(r"<[^>]+>", "", raw).strip().strip('"')
        return cleaned

    @staticmethod
    def _split_addresses(raw: str | None) -> list[str]:
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]

    def _extract_text_body(self, message: Message) -> str:
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition") or "")
                if content_type == "text/plain" and "attachment" not in disposition.lower():
                    payload = part.get_payload(decode=True)
                    if payload is None or not isinstance(payload, bytes):
                        continue
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        payload = message.get_payload(decode=True)
        if payload is None or not isinstance(payload, bytes):
            return ""
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")

    def _mark_synced(self, user_id: str) -> None:
        try:
            self._connections.mark_synced_by_user_id(user_id=user_id, provider=IntegrationProvider.IMAP)
        except Exception:  # noqa: BLE001
            pass
