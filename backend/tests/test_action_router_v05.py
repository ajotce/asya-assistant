from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.services.action_router import ActionRouter


def _router(tool_handlers=None):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    return ActionRouter(session=session, pending_store={}, tool_handlers=tool_handlers or {})


def test_intent_github_prs_read_without_confirmation() -> None:
    called = {"value": 0}

    def _handler(*, user_id: str, query: str) -> str:
        called["value"] += 1
        return "PR: 3 обновления"

    router = _router({("github", "prs"): _handler})
    result = router.handle(user_id="u1", session_id="s1", message="что нового в моих PR?")

    assert result.handled is True
    assert result.pending_action_id is None
    assert "PR: 3" in result.message
    assert called["value"] == 1


def test_intent_bitrix_funnel_sum_read_without_confirmation() -> None:
    router = _router({("bitrix", "funnel_sum"): lambda **_: "Воронка: 1 250 000"})
    result = router.handle(
        user_id="u1",
        session_id="s1",
        message="сколько денег в воронке X на стадии Y?",
    )
    assert result.handled is True
    assert result.pending_action_id is None
    assert "1 250 000" in result.message


def test_intent_storage_search_read_without_confirmation() -> None:
    router = _router({("storage", "search"): lambda **_: "Найдено 2 файла в Яндекс.Диске"})
    result = router.handle(user_id="u1", session_id="s1", message="найди файл в Яндекс.Диске")
    assert result.handled is True
    assert result.pending_action_id is None
    assert "2 файла" in result.message


def test_intent_document_template_fill_without_confirmation() -> None:
    router = _router({("document", "template_fill"): lambda **_: "Гарантийный талон сгенерирован"})
    result = router.handle(user_id="u1", session_id="s1", message="сделай гарантийный талон на холодильник")
    assert result.handled is True
    assert result.pending_action_id is None
    assert "сгенерирован" in result.message


def test_intent_briefing_generate_without_confirmation() -> None:
    router = _router({("briefing", "generate"): lambda **_: "Вечерний итог готов"})
    result = router.handle(user_id="u1", session_id="s1", message="сгенерируй вечерний итог")
    assert result.handled is True
    assert result.pending_action_id is None
    assert "итог" in result.message.lower()


def test_intent_rollback_preview_without_confirmation() -> None:
    router = _router({("rollback", "preview"): lambda **_: "Предпросмотр отката: действие #42"})
    result = router.handle(user_id="u1", session_id="s1", message="откати последнее действие")
    assert result.handled is True
    assert result.pending_action_id is None
    assert "предпросмотр" in result.message.lower()


def test_storage_save_requires_confirmation_and_no_hidden_write() -> None:
    called = {"value": 0}

    def _handler(**_) -> str:
        called["value"] += 1
        return "Файл сохранён"

    router = _router({("storage", "save"): _handler})
    first = router.handle(user_id="u1", session_id="s1", message="/tool storage save report.txt")

    assert first.handled is True
    assert first.pending_action_id is not None
    assert called["value"] == 0

    second = router.handle(
        user_id="u1",
        session_id="s1",
        message=f"/confirm {first.pending_action_id}",
    )
    assert second.handled is True
    assert "сохран" in second.message.lower()
    assert called["value"] == 1


def test_rollback_execute_requires_confirmation() -> None:
    called = {"value": 0}

    def _handler(**_) -> str:
        called["value"] += 1
        return "Rollback выполнен"

    router = _router({("rollback", "execute"): _handler})
    first = router.handle(user_id="u1", session_id="s1", message="/tool rollback execute last")

    assert first.handled is True
    assert first.pending_action_id is not None
    assert called["value"] == 0

    router.handle(user_id="u1", session_id="s1", message=f"/confirm {first.pending_action_id}")
    assert called["value"] == 1


def test_storage_share_requires_confirmation_and_no_hidden_write() -> None:
    called = {"value": 0}

    def _handler(**_) -> str:
        called["value"] += 1
        return "Файл расшарен"

    router = _router({("storage", "share"): _handler})
    first = router.handle(user_id="u1", session_id="s1", message="/tool storage share report.txt")

    assert first.handled is True
    assert first.pending_action_id is not None
    assert called["value"] == 0

    second = router.handle(
        user_id="u1",
        session_id="s1",
        message=f"/confirm {first.pending_action_id}",
    )
    assert second.handled is True
    assert "расшар" in second.message.lower()
    assert called["value"] == 1


def test_storage_delete_requires_confirmation_and_no_hidden_write() -> None:
    called = {"value": 0}

    def _handler(**_) -> str:
        called["value"] += 1
        return "Файл удалён"

    router = _router({("storage", "delete"): _handler})
    first = router.handle(user_id="u1", session_id="s1", message="/tool storage delete report.txt")

    assert first.handled is True
    assert first.pending_action_id is not None
    assert called["value"] == 0

    second = router.handle(
        user_id="u1",
        session_id="s1",
        message=f"/confirm {first.pending_action_id}",
    )
    assert second.handled is True
    assert "удал" in second.message.lower()
    assert called["value"] == 1
