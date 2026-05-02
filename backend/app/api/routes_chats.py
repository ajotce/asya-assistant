from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import ChatKind
from app.db.models.user import User
from app.models.schemas import (
    ChatCreateRequest,
    ChatListItemResponse,
    ChatMessageItemResponse,
    ChatRenameRequest,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_meta_repository import FileMetaRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.usage_record_repository import UsageRecordRepository
from app.services.chat_service_v2 import ChatNotFoundError, ChatServiceV2, ProtectedBaseChatError
from app.storage.runtime import file_store, usage_store, vector_store

router = APIRouter(tags=["chats"])


@router.get("/chats", response_model=list[ChatListItemResponse])
def list_chats(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ChatListItemResponse]:
    service = ChatServiceV2(db_session)
    chats = service.list_chats(current_user.id)
    message_repo = MessageRepository(db_session)
    return [
        ChatListItemResponse(
            id=chat.id,
            title=chat.title,
            kind=chat.kind.value,
            is_archived=chat.is_archived,
            created_at=chat.created_at.isoformat(),
            updated_at=chat.updated_at.isoformat(),
            message_count=message_repo.count_for_chat(chat.id),
        )
        for chat in chats
    ]


@router.post("/chats", response_model=ChatListItemResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ChatListItemResponse:
    chat = ChatServiceV2(db_session).create_chat(current_user.id, payload.title)
    return ChatListItemResponse(
        id=chat.id,
        title=chat.title,
        kind=chat.kind.value,
        is_archived=chat.is_archived,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=0,
    )


@router.patch("/chats/{chat_id}", response_model=ChatListItemResponse)
def rename_chat(
    chat_id: str,
    payload: ChatRenameRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ChatListItemResponse:
    service = ChatServiceV2(db_session)
    try:
        chat = service.rename_chat(current_user.id, chat_id, payload.title)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatListItemResponse(
        id=chat.id,
        title=chat.title,
        kind=chat.kind.value,
        is_archived=chat.is_archived,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=MessageRepository(db_session).count_for_chat(chat.id),
    )


@router.post("/chats/{chat_id}/archive", response_model=ChatListItemResponse)
def archive_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ChatListItemResponse:
    service = ChatServiceV2(db_session)
    try:
        chat = service.archive_chat(current_user.id, chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProtectedBaseChatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatListItemResponse(
        id=chat.id,
        title=chat.title,
        kind=chat.kind.value,
        is_archived=chat.is_archived,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=MessageRepository(db_session).count_for_chat(chat.id),
    )


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Response:
    service = ChatServiceV2(db_session)
    try:
        chat = service.delete_chat(current_user.id, chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProtectedBaseChatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if chat.kind != ChatKind.BASE:
        file_store.delete_session_files(chat_id)
        vector_store.delete_session(chat_id)
        usage_store.delete_session(chat_id)
        FileMetaRepository(db_session).delete_for_chat_user(chat_id=chat_id, user_id=current_user.id)
        UsageRecordRepository(db_session).delete_for_chat_user(user_id=current_user.id, chat_id=chat_id)
        db_session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/chats/{chat_id}/messages", response_model=list[ChatMessageItemResponse])
def get_chat_messages(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ChatMessageItemResponse]:
    chat = ChatRepository(db_session).get_for_user(chat_id, current_user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Чат не найден.")
    messages = MessageRepository(db_session).list_for_chat(chat_id)
    return [
        ChatMessageItemResponse(
            id=message.id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at.isoformat(),
        )
        for message in messages
    ]
