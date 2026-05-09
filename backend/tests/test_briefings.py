from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.common import BriefingKind
from app.db.session import get_engine
from app.services.briefing_service import BriefingService
from tests.auth_helpers import build_authed_client, setup_test_db


class _FakeResponse:
    status_code = 200

    @staticmethod
    def json() -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": "## Briefing\n\n- line 1\n- line 2",
                    }
                }
            ]
        }


def test_generate_morning_and_evening_briefings(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _FakeResponse())
    client = build_authed_client(tmp_path, monkeypatch, email="briefings@example.com")

    morning = client.post("/api/briefings/generate?kind=morning")
    evening = client.post("/api/briefings/generate?kind=evening")

    assert morning.status_code == 200
    assert evening.status_code == 200
    assert morning.json()["kind"] == "morning"
    assert evening.json()["kind"] == "evening"

    listed = client.get("/api/briefings?days=30&limit=30")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) >= 2


def test_delivery_only_to_enabled_channels(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _FakeResponse())
    client = build_authed_client(tmp_path, monkeypatch, email="channels@example.com")

    patch = client.patch(
        "/api/briefings/settings",
        json={
            "timezone": "Europe/Moscow",
            "morning_enabled": True,
            "evening_enabled": True,
            "morning_time": "08:00",
            "evening_time": "19:00",
            "channel_in_app": True,
            "channel_telegram": False,
        },
    )
    assert patch.status_code == 200

    response = client.post("/api/briefings/generate?kind=morning")
    assert response.status_code == 200
    assert response.json()["delivered_via"] == ["in_app"]


def test_cleanup_deletes_briefings_older_than_30_days(tmp_path, monkeypatch):
    _, engine = setup_test_db(tmp_path, monkeypatch)
    Base.metadata.create_all(engine)

    with Session(bind=engine) as session:
        user_id = "u-cleanup"
        session.execute(
            text(
                "INSERT INTO users (id, email, display_name, password_hash, role, status, created_at, updated_at) "
                "VALUES (:id, :email, :display_name, :password_hash, :role, :status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": user_id,
                "email": "cleanup@example.com",
                "display_name": "Cleanup",
                "password_hash": None,
                "role": "user",
                "status": "active",
            },
        )
        session.commit()

        monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _FakeResponse())
        service = BriefingService(session)
        old_item = service.generate(user_id=user_id, kind=BriefingKind.MORNING)
        fresh_item = service.generate(user_id=user_id, kind=BriefingKind.EVENING)
        old_id = old_item.id
        fresh_id = fresh_item.id

        old_item.created_at = datetime.now(timezone.utc) - timedelta(days=31)
        session.add(old_item)
        session.commit()

        deleted = service.cleanup_old(days=30)
        assert deleted >= 1

        remaining = service.list_recent(user_id=user_id, days=365, limit=20)
        remaining_ids = {item.id for item in remaining}
        assert fresh_id in remaining_ids
        assert old_id not in remaining_ids

    get_settings.cache_clear()
    get_engine.cache_clear()
