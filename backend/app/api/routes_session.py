from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.common import ChatKind
from app.db.models.user import User
from app.models.schemas import SessionCreateResponse, SessionFilesUploadResponse, SessionStateResponse
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_meta_repository import FileMetaRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.usage_record_repository import UsageRecordRepository
from app.services.chat_service_v2 import ChatServiceV2
from app.services.file_service import FileService, FileValidationError
from app.services.usage_recorder import UsageRecorder
from app.services.vsellm_client import VseLLMClient
from app.storage.runtime import file_store, usage_store, vector_store
from sqlalchemy.orm import Session

router = APIRouter(tags=["session"])


@router.post("/session", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SessionCreateResponse:
    chat = ChatRepository(db_session).create(
        user_id=current_user.id,
        title="Новый чат",
        kind=ChatKind.REGULAR,
    )
    db_session.commit()
    db_session.refresh(chat)
    return SessionCreateResponse(session_id=chat.id, created_at=chat.created_at.isoformat())


@router.get("/session/{session_id}", response_model=SessionStateResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SessionStateResponse:
    chat_service = ChatServiceV2(db_session)
    chat_service.ensure_single_active_base_chat(current_user.id)
    chat = ChatRepository(db_session).get_for_user(session_id, current_user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return SessionStateResponse(
        session_id=chat.id,
        created_at=chat.created_at.isoformat(),
        message_count=MessageRepository(db_session).count_for_chat(chat.id),
        file_ids=[item.file_id for item in file_store.get_session_files(chat.id)],
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Response:
    chat_repo = ChatRepository(db_session)
    chat = chat_repo.get_for_user(session_id, current_user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    if chat.kind == ChatKind.BASE:
        raise HTTPException(status_code=400, detail="Нельзя удалить Base-chat.")
    file_store.delete_session_files(session_id)
    vector_store.delete_session(session_id)
    usage_store.delete_session(session_id)
    FileMetaRepository(db_session).delete_for_chat_user(chat_id=session_id, user_id=current_user.id)
    UsageRecordRepository(db_session).delete_for_chat_user(user_id=current_user.id, chat_id=session_id)
    chat.is_deleted = True
    chat.is_archived = True
    chat_repo.save(chat)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def get_file_service(current_user: User, db_session: Session) -> FileService:
    settings = get_settings()
    chat_repo = ChatRepository(db_session)
    usage_repo = UsageRecordRepository(db_session)
    return FileService(
        settings=settings,
        chat_repository=chat_repo,
        current_user_id=current_user.id,
        file_meta_repository=FileMetaRepository(db_session),
        file_store=file_store,
        vector_store=vector_store,
        vsellm_client=VseLLMClient(settings),
        usage_recorder=UsageRecorder(
            settings=settings,
            user_id=current_user.id,
            chat_repository=chat_repo,
            usage_repository=usage_repo,
        ),
        usage_store=usage_store,
    )


@router.post("/session/{session_id}/files", response_model=SessionFilesUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_files_to_session(
    session_id: str,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SessionFilesUploadResponse:
    service = get_file_service(current_user=current_user, db_session=db_session)
    try:
        uploaded = await service.upload_files(session_id=session_id, files=files)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc
    db_session.commit()

    chat = ChatRepository(db_session).get_for_user(session_id, current_user.id)
    if chat is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return SessionFilesUploadResponse(
        session_id=session_id,
        files=uploaded,
        file_ids=[item.file_id for item in file_store.get_session_files(session_id)],
    )
