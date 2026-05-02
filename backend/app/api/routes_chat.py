from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.models.schemas import ChatStreamRequest
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.usage_record_repository import UsageRecordRepository
from app.services.chat_service import ChatService
from app.services.usage_recorder import UsageRecorder
from app.services.vsellm_client import VseLLMClient
from app.storage.runtime import file_store, usage_store, vector_store
from sqlalchemy.orm import Session

router = APIRouter(tags=["chat"])


def get_chat_service(current_user: User, db_session: Session) -> ChatService:
    settings = get_settings()
    chat_repo = ChatRepository(db_session)
    return ChatService(
        settings=settings,
        current_user_id=current_user.id,
        chat_repository=chat_repo,
        message_repository=MessageRepository(db_session),
        file_store=file_store,
        vector_store=vector_store,
        vsellm_client=VseLLMClient(settings),
        usage_recorder=UsageRecorder(
            settings=settings,
            user_id=current_user.id,
            chat_repository=chat_repo,
            usage_repository=UsageRecordRepository(db_session),
        ),
        usage_store=usage_store,
    )


@router.post("/chat/stream")
def stream_chat(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> StreamingResponse:
    service = get_chat_service(current_user=current_user, db_session=db_session)
    stream = service.stream_chat(
        session_id=request.session_id,
        user_message=request.message,
        file_ids=request.file_ids,
    )
    return StreamingResponse(stream, media_type="text/event-stream")
