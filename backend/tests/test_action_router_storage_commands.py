from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.action_router import ActionRouter
from tests.auth_helpers import setup_test_db


def test_action_router_parses_natural_storage_create(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    with Session(bind=engine) as session:
        router = ActionRouter(session, pending_store={})
        result = router.handle(
            user_id="user-1",
            session_id="chat-1",
            message="Сохрани файл в OneDrive в папку договоры",
        )
        assert result.handled is True
        assert result.pending_action_id is not None
        assert "Подтвердите действие" in result.message


def test_action_router_parses_natural_storage_search(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    with Session(bind=engine) as session:
        router = ActionRouter(session, pending_store={})
        result = router.handle(
            user_id="user-1",
            session_id="chat-1",
            message="Найди документ в моих файлах по слову договор",
        )
        assert result.handled is True
        assert result.pending_action_id is not None
