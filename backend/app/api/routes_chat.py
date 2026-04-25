from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models.schemas import ChatStreamRequest
from app.services.chat_service import ChatService
from app.storage.session_store import SessionStore

router = APIRouter(tags=["chat"])
session_store = SessionStore()


def get_chat_service() -> ChatService:
    return ChatService(settings=get_settings(), session_store=session_store)


@router.post("/chat/stream")
def stream_chat(request: ChatStreamRequest) -> StreamingResponse:
    service = get_chat_service()
    stream = service.stream_chat(session_id=request.session_id, user_message=request.message)
    return StreamingResponse(stream, media_type="text/event-stream")
