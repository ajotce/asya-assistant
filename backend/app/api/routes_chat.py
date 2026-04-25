from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models.schemas import ChatStreamRequest
from app.services.chat_service import ChatService
from app.services.vsellm_client import VseLLMClient
from app.storage.runtime import file_store, session_store, usage_store, vector_store

router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(
        settings=settings,
        session_store=session_store,
        file_store=file_store,
        vector_store=vector_store,
        vsellm_client=VseLLMClient(settings),
        usage_store=usage_store,
    )


@router.post("/chat/stream")
def stream_chat(request: ChatStreamRequest) -> StreamingResponse:
    service = get_chat_service()
    stream = service.stream_chat(
        session_id=request.session_id,
        user_message=request.message,
        file_ids=request.file_ids,
    )
    return StreamingResponse(stream, media_type="text/event-stream")
