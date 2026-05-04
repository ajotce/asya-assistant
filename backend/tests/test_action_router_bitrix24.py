from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.services.action_router import ActionRouter


def _router() -> ActionRouter:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    return ActionRouter(session=session, pending_store={})


def test_tool_bitrix24_leads_by_source(monkeypatch) -> None:
    router = _router()

    def _fake_list_leads(self, *, user_id: str, source_id=None, created_since=None):
        return {"result": [{"ID": "1"}, {"ID": "2"}], "total": 2}

    monkeypatch.setattr("app.integrations.bitrix24.Bitrix24Service.list_leads", _fake_list_leads)
    result = router.handle(
        user_id="u1",
        session_id="s1",
        message="сколько лидов сегодня пришло из источника yandex_direct?",
    )
    assert result.handled is True
    assert "2" in result.message


def test_tool_bitrix24_deals_period(monkeypatch) -> None:
    router = _router()

    def _fake_list_deals(self, *, user_id: str, date_from=None, date_to=None):
        return {"result": [{"ID": "10"}], "total": 1}

    monkeypatch.setattr("app.integrations.bitrix24.Bitrix24Service.list_deals", _fake_list_deals)
    result = router.handle(
        user_id="u1",
        session_id="s1",
        message="покажи сделки за период 2026-01-01 2026-01-31",
    )
    assert result.handled is True
    assert "1" in result.message
