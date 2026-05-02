from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db import models as _db_models  # noqa: F401
from app.services.chat_service_v2 import ChatNotFoundError, ChatServiceV2, ProtectedBaseChatError
from app.services.user_service import UserService


def _make_session(tmp_path) -> Session:
    db_path = tmp_path / "user-chat-services.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    return session_factory()


def test_create_user_auto_creates_single_active_base_chat(tmp_path) -> None:
    session = _make_session(tmp_path)
    user_service = UserService(session)
    chat_service = ChatServiceV2(session)

    user = user_service.create_user(email="a@example.com", display_name="User A")
    chats = chat_service.list_chats(user.id)
    base_chats = [chat for chat in chats if chat.kind.value == "base" and not chat.is_archived and not chat.is_deleted]

    assert len(base_chats) == 1
    assert base_chats[0].title == "Base-chat"


def test_chat_crud_and_safe_delete(tmp_path) -> None:
    session = _make_session(tmp_path)
    user = UserService(session).create_user(email="owner@example.com", display_name="Owner")
    chat_service = ChatServiceV2(session)

    new_chat = chat_service.create_chat(user.id, "Рабочий чат")
    assert new_chat.title == "Рабочий чат"

    renamed = chat_service.rename_chat(user.id, new_chat.id, "Переименованный чат")
    assert renamed.title == "Переименованный чат"

    archived = chat_service.archive_chat(user.id, new_chat.id)
    assert archived.is_archived is True
    assert archived.is_deleted is False

    deleted = chat_service.delete_chat(user.id, new_chat.id)
    assert deleted.is_deleted is True
    assert deleted.is_archived is True

    chats = chat_service.list_chats(user.id)
    assert all(chat.id != new_chat.id for chat in chats)


def test_base_chat_is_protected_from_archive_and_delete(tmp_path) -> None:
    session = _make_session(tmp_path)
    user = UserService(session).create_user(email="base@example.com", display_name="Base User")
    chat_service = ChatServiceV2(session)
    base_chat = chat_service.list_chats(user.id)[0]

    try:
        chat_service.archive_chat(user.id, base_chat.id)
        assert False, "Expected ProtectedBaseChatError"
    except ProtectedBaseChatError:
        pass

    try:
        chat_service.delete_chat(user.id, base_chat.id)
        assert False, "Expected ProtectedBaseChatError"
    except ProtectedBaseChatError:
        pass


def test_chat_isolation_user_a_cannot_access_user_b_chat(tmp_path) -> None:
    session = _make_session(tmp_path)
    user_service = UserService(session)
    chat_service = ChatServiceV2(session)

    user_a = user_service.create_user(email="usera@example.com", display_name="User A")
    user_b = user_service.create_user(email="userb@example.com", display_name="User B")

    chat_b = chat_service.create_chat(user_b.id, "Чат B")

    listed_for_a = chat_service.list_chats(user_a.id)
    assert all(chat.id != chat_b.id for chat in listed_for_a)

    try:
        chat_service.get_chat(user_a.id, chat_b.id)
        assert False, "Expected ChatNotFoundError"
    except ChatNotFoundError:
        pass
