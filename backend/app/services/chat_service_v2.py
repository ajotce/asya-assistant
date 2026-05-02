from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.chat import Chat
from app.db.models.user import User
from app.db.models.common import ChatKind
from app.repositories.chat_repository import ChatRepository
from app.repositories.user_repository import UserRepository
from app.services.private_chat_crypto import generate_private_salt
from app.services.space_service import SpaceService


class ChatNotFoundError(ValueError):
    pass


class ProtectedBaseChatError(ValueError):
    pass


class ChatServiceV2:
    def __init__(self, session: Session, chat_repository: Optional[ChatRepository] = None) -> None:
        self._session = session
        self._chats = chat_repository or ChatRepository(session)
        self._spaces = SpaceService(session)
        self._users = UserRepository(session)

    def ensure_single_active_base_chat(self, user_id: str, *, space_id: str | None = None) -> Chat:
        base_chats = self._chats.list_base_chats(user_id)

        if not base_chats:
            base_chat = self._chats.create(
                user_id=user_id,
                space_id=space_id,
                title="Base-chat",
                kind=ChatKind.BASE,
                is_archived=False,
            )
            self._session.flush()
            return base_chat

        active_chat: Optional[Chat] = None
        for chat in base_chats:
            if chat.is_archived:
                continue
            active_chat = chat
            break

        if active_chat is None:
            active_chat = base_chats[0]
            active_chat.is_archived = False
            self._chats.save(active_chat)

        for chat in base_chats:
            if chat.id == active_chat.id:
                continue
            if not chat.is_archived:
                chat.is_archived = True
                self._chats.save(chat)

        self._session.flush()
        return active_chat

    def list_chats(self, user_id: str) -> list[Chat]:
        self.ensure_single_active_base_chat(user_id)
        self._session.flush()
        return self._chats.list_for_user(user_id)

    def get_preferred_chat(self, user_id: str) -> Chat:
        chats = self.list_chats(user_id)
        active = [chat for chat in chats if not chat.is_deleted and not chat.is_archived]
        if not active:
            return self.ensure_single_active_base_chat(user_id)
        return active[-1]

    def get_chat(self, user_id: str, chat_id: str) -> Chat:
        chat = self._chats.get_for_user(chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Чат не найден.")
        return chat

    def create_chat(
        self,
        user: User | str,
        title: str,
        *,
        space_id: str | None = None,
        kind: ChatKind = ChatKind.REGULAR,
    ) -> Chat:
        resolved_user = user if isinstance(user, User) else self._users.get_by_id(user)
        if resolved_user is None:
            raise ChatNotFoundError("Пользователь не найден.")

        resolved_space_id = None
        if space_id is not None:
            resolved_space = self._spaces.get_space_for_user(user=resolved_user, space_id=space_id)
            resolved_space_id = resolved_space.id
        else:
            resolved_space_id = self._spaces.get_default_space(resolved_user).id

        chat = self._chats.create(
            user_id=resolved_user.id,
            space_id=resolved_space_id,
            title=title.strip() or "Новый чат",
            kind=kind,
        )
        if kind == ChatKind.PRIVATE_ENCRYPTED:
            chat.private_salt = generate_private_salt()
        self._session.commit()
        self._session.refresh(chat)
        return chat

    def rename_chat(self, user_id: str, chat_id: str, title: str) -> Chat:
        chat = self.get_chat(user_id, chat_id)
        chat.title = title.strip() or chat.title
        self._chats.save(chat)
        self._session.commit()
        self._session.refresh(chat)
        return chat

    def archive_chat(self, user_id: str, chat_id: str) -> Chat:
        chat = self.get_chat(user_id, chat_id)
        if chat.kind == ChatKind.BASE:
            raise ProtectedBaseChatError("Нельзя архивировать Base-chat.")
        chat.is_archived = True
        self._chats.save(chat)
        self._session.commit()
        self._session.refresh(chat)
        return chat

    def delete_chat(self, user_id: str, chat_id: str) -> Chat:
        chat = self.get_chat(user_id, chat_id)
        if chat.kind == ChatKind.BASE:
            raise ProtectedBaseChatError("Нельзя удалить Base-chat.")
        chat.is_deleted = True
        chat.is_archived = True
        self._chats.save(chat)
        self._session.commit()
        self._session.refresh(chat)
        return chat
