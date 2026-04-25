from fastapi import APIRouter, HTTPException, Response, status

from app.models.schemas import SessionCreateResponse, SessionFileBindRequest, SessionStateResponse
from app.storage.runtime import session_store

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
    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/session/{session_id}/files", response_model=SessionStateResponse)
def bind_file_to_session(session_id: str, request: SessionFileBindRequest) -> SessionStateResponse:
    file_id = request.file_id.strip()
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id обязателен.")

    session = session_store.bind_file(session_id=session_id, file_id=file_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return SessionStateResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        message_count=len(session.messages),
        file_ids=session.file_ids,
    )
