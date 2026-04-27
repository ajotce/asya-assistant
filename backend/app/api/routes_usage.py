from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import (
    UsageCostInfo,
    UsageEmbeddingsInfo,
    UsageOverviewResponse,
    UsageRuntimeInfo,
    UsageSessionResponse,
    UsageSessionRuntimeInfo,
    UsageTokensInfo,
)
from app.services.settings_service import SettingsService
from app.storage.runtime import session_store, usage_store, vector_store
from app.storage.usage_store import ChatUsageAggregate, EmbeddingsUsageAggregate

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


@router.get("/usage", response_model=UsageOverviewResponse)
def get_usage_overview() -> UsageOverviewResponse:
    settings = get_settings()
    runtime_settings = SettingsService(settings).get_settings()
    return UsageOverviewResponse(
        chat=_chat_usage_to_schema(usage_store.get_chat_total()),
        embeddings=_embeddings_usage_to_schema(usage_store.get_embeddings_total()),
        cost=_unavailable_cost(),
        runtime=UsageRuntimeInfo(
            active_sessions=session_store.active_sessions_count(),
            selected_model=runtime_settings.selected_model,
            embedding_model=settings.default_embedding_model,
        ),
    )


@router.get("/usage/session/{session_id}", response_model=UsageSessionResponse)
def get_usage_for_session(session_id: str) -> UsageSessionResponse:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")

    user_messages = sum(1 for message in session.messages if message.get("role") == "user")
    assistant_messages = sum(1 for message in session.messages if message.get("role") == "assistant")

    return UsageSessionResponse(
        chat=_chat_usage_to_schema(usage_store.get_chat_for_session(session_id)),
        embeddings=_embeddings_usage_to_schema(usage_store.get_embeddings_for_session(session_id)),
        cost=_unavailable_cost(),
        runtime=UsageSessionRuntimeInfo(
            session_id=session.session_id,
            created_at=session.created_at,
            message_count=len(session.messages),
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            file_count=len(session.file_ids),
            chunks_indexed=vector_store.count_session_chunks(session_id),
        ),
    )
