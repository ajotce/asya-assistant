from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.models.schemas import (
    UsageCostInfo,
    UsageEmbeddingsInfo,
    UsageOverviewResponse,
    UsageRuntimeInfo,
    UsageSessionResponse,
    UsageSessionRuntimeInfo,
    UsageTokensInfo,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_meta_repository import FileMetaRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.usage_record_repository import UsageRecordAggregate, UsageRecordRepository
from app.services.settings_service import SettingsService
from app.storage.runtime import vector_store
from app.storage.usage_store import ChatUsageAggregate, EmbeddingsUsageAggregate
from sqlalchemy.orm import Session

router = APIRouter(tags=["usage"])


def _chat_usage_to_schema(usage: ChatUsageAggregate) -> UsageTokensInfo:
    if usage.requests_count == 0:
        return UsageTokensInfo(
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            status="unavailable",
            note="Данные usage по chat пока не собраны.",
        )
    return UsageTokensInfo(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        status="available",
        note=None,
    )


def _embeddings_usage_to_schema(usage: EmbeddingsUsageAggregate) -> UsageEmbeddingsInfo:
    if usage.requests_count == 0:
        return UsageEmbeddingsInfo(
            input_tokens=None,
            total_tokens=None,
            status="unavailable",
            note="Данные usage по embeddings пока не собраны.",
        )
    return UsageEmbeddingsInfo(
        input_tokens=usage.input_tokens,
        total_tokens=usage.total_tokens,
        status="available",
        note=None,
    )


def _unavailable_cost() -> UsageCostInfo:
    return UsageCostInfo(
        currency=None,
        total_cost=None,
        status="unavailable",
        note="Стоимость не рассчитывается: цены моделей не хардкодятся в приложении.",
    )


def _chat_record_to_aggregate(agg: UsageRecordAggregate) -> ChatUsageAggregate:
    return ChatUsageAggregate(
        prompt_tokens=agg.prompt_tokens,
        completion_tokens=agg.completion_tokens,
        total_tokens=agg.total_tokens,
        requests_count=agg.requests_count,
    )


def _emb_record_to_aggregate(agg: UsageRecordAggregate) -> EmbeddingsUsageAggregate:
    return EmbeddingsUsageAggregate(
        input_tokens=agg.prompt_tokens,
        total_tokens=agg.total_tokens,
        requests_count=agg.requests_count,
    )


@router.get("/usage", response_model=UsageOverviewResponse)
def get_usage_overview(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> UsageOverviewResponse:
    settings = get_settings()
    runtime_settings = SettingsService(settings).get_settings()
    usage_repo = UsageRecordRepository(db_session)
    active_sessions = len(ChatRepository(db_session).list_for_user(current_user.id))
    return UsageOverviewResponse(
        chat=_chat_usage_to_schema(_chat_record_to_aggregate(usage_repo.aggregate_for_user(user_id=current_user.id, kind="chat"))),
        embeddings=_embeddings_usage_to_schema(
            _emb_record_to_aggregate(usage_repo.aggregate_for_user(user_id=current_user.id, kind="embeddings"))
        ),
        cost=_unavailable_cost(),
        runtime=UsageRuntimeInfo(
            active_sessions=active_sessions,
            selected_model=runtime_settings.selected_model,
            embedding_model=settings.default_embedding_model,
        ),
    )


@router.get("/usage/session/{session_id}", response_model=UsageSessionResponse)
def get_usage_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> UsageSessionResponse:
    chat_repo = ChatRepository(db_session)
    message_repo = MessageRepository(db_session)
    usage_repo = UsageRecordRepository(db_session)
    chat = chat_repo.get_for_user(session_id, current_user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")

    messages = message_repo.list_for_chat(session_id)
    user_messages = sum(1 for message in messages if message.role.value == "user")
    assistant_messages = sum(1 for message in messages if message.role.value == "assistant")
    file_count = len(FileMetaRepository(db_session).list_for_chat_user(chat_id=session_id, user_id=current_user.id))

    return UsageSessionResponse(
        chat=_chat_usage_to_schema(
            _chat_record_to_aggregate(usage_repo.aggregate_for_chat_user(user_id=current_user.id, chat_id=session_id, kind="chat"))
        ),
        embeddings=_embeddings_usage_to_schema(
            _emb_record_to_aggregate(
                usage_repo.aggregate_for_chat_user(user_id=current_user.id, chat_id=session_id, kind="embeddings")
            )
        ),
        cost=_unavailable_cost(),
        runtime=UsageSessionRuntimeInfo(
            session_id=chat.id,
            created_at=chat.created_at.isoformat(),
            message_count=len(messages),
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            file_count=file_count,
            chunks_indexed=vector_store.count_session_chunks(session_id),
        ),
    )
