from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.core.config import get_settings
from app.models.schemas import SessionCreateResponse, SessionFilesUploadResponse, SessionStateResponse
from app.services.file_service import FileService, FileValidationError
from app.services.vsellm_client import VseLLMClient
from app.storage.runtime import file_store, session_store, usage_store, vector_store

router = APIRouter(tags=["session"])


@router.post("/session", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session() -> SessionCreateResponse:
    session = session_store.create_session()
    return SessionCreateResponse(session_id=session.session_id, created_at=session.created_at)


@router.get("/session/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str) -> SessionStateResponse:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return SessionStateResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        message_count=len(session.messages),
        file_ids=session.file_ids,
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    if not session_store.has_session(session_id):
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    file_store.delete_session_files(session_id)
    vector_store.delete_session(session_id)
    usage_store.delete_session(session_id)
    deleted = session_store.delete_session(session_id)
    if not deleted:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def get_file_service() -> FileService:
    settings = get_settings()
    return FileService(
        settings=settings,
        session_store=session_store,
        file_store=file_store,
        vector_store=vector_store,
        vsellm_client=VseLLMClient(settings),
        usage_store=usage_store,
    )


@router.post("/session/{session_id}/files", response_model=SessionFilesUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_files_to_session(session_id: str, files: list[UploadFile] = File(...)) -> SessionFilesUploadResponse:
    service = get_file_service()
    try:
        uploaded = await service.upload_files(session_id=session_id, files=files)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    session = session_store.get_session(session_id)
    if session is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return SessionFilesUploadResponse(
        session_id=session_id,
        files=uploaded,
        file_ids=session.file_ids,
    )
