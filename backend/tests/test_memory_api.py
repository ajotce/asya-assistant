from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.main import app


def _setup_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "memory-api.sqlite3"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    monkeypatch.setenv("AUTH_REGISTRATION_MODE", "open")
    monkeypatch.setenv("AUTH_SESSION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_COOKIE_NAME", "asya_session")
    get_settings.cache_clear()
    get_engine.cache_clear()
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    Base.metadata.create_all(engine)
    return engine


def _override_db_session(engine):
    def _override():
        session = Session(bind=engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _override


def _register_and_login(client: TestClient, email: str, display_name: str) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": display_name, "password": "strong-pass-123"},
    )
    assert reg.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def test_foreign_memory_is_not_accessible(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "mema@example.com", "A")
    _register_and_login(client_b, "memb@example.com", "B")

    created = client_a.post(
        "/api/memory/facts",
        json={"key": "favorite_food", "value": "pizza", "status": "confirmed", "source": "user"},
    )
    assert created.status_code == 200
    fact_id = created.json()["id"]

    get_by_b = client_b.patch(
        f"/api/memory/facts/{fact_id}",
        json={"key": "favorite_food", "value": "salad", "source": "user"},
    )
    assert get_by_b.status_code == 404

    status_by_b = client_b.post(f"/api/memory/facts/{fact_id}/status", json={"status": "forbidden"})
    assert status_by_b.status_code == 404
    app.dependency_overrides.clear()


def test_status_change_creates_version_record(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "memstatus@example.com", "Status")

    created = client.post(
        "/api/memory/facts",
        json={"key": "timezone", "value": "Europe/Moscow", "status": "inferred", "source": "assistant"},
    )
    assert created.status_code == 200
    fact_id = created.json()["id"]

    changed = client.post(f"/api/memory/facts/{fact_id}/status", json={"status": "confirmed"})
    assert changed.status_code == 200

    changes = client.get("/api/memory/changes")
    assert changes.status_code == 200
    fact_changes = [item for item in changes.json() if item["entity_id"] == fact_id]
    assert any(item["change_kind"] == "status" for item in fact_changes)
    status_change = next(item for item in fact_changes if item["change_kind"] == "status")
    assert status_change["old_value"]["status"] == "inferred"
    assert status_change["new_value"]["status"] == "confirmed"
    app.dependency_overrides.clear()


def test_forbidden_memory_not_in_active_list(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "memforbid@example.com", "Forbid")

    created = client.post(
        "/api/memory/facts",
        json={"key": "phone", "value": "123", "status": "confirmed", "source": "user"},
    )
    assert created.status_code == 200
    fact_id = created.json()["id"]

    forbidden = client.post(f"/api/memory/facts/{fact_id}/forbid")
    assert forbidden.status_code == 200
    assert forbidden.json()["status"] == "forbidden"

    active = client.get("/api/memory/facts")
    assert active.status_code == 200
    assert all(item["id"] != fact_id for item in active.json())

    all_facts = client.get("/api/memory/facts", params={"active_only": "false"})
    assert all_facts.status_code == 200
    assert any(item["id"] == fact_id for item in all_facts.json())
    app.dependency_overrides.clear()


def test_activity_log_is_created_for_memory_operations(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "memlog@example.com", "Log")

    fact = client.post(
        "/api/memory/facts",
        json={"key": "lang", "value": "ru", "status": "confirmed", "source": "user"},
    )
    assert fact.status_code == 200

    rule = client.post(
        "/api/memory/rules",
        json={
            "title": "Tone",
            "instruction": "Пиши кратко",
            "scope": "user",
            "strictness": "normal",
            "source": "user",
            "status": "active",
        },
    )
    assert rule.status_code == 200

    logs = client.get("/api/activity-log")
    assert logs.status_code == 200
    event_types = {item["event_type"] for item in logs.json()}
    assert "memory_fact_created" in event_types
    assert "rule_applied" in event_types
    app.dependency_overrides.clear()


def test_personality_profile_update_and_overlay_api(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "persona@example.com", "Persona")

    base = client.get("/api/personality")
    assert base.status_code == 200
    assert base.json()["scope"] == "base"
    assert base.json()["humor_level"] == 1

    updated = client.put(
        "/api/personality",
        json={
            "name": "Asya",
            "tone": "calm",
            "style_notes": "Без воды",
            "humor_level": 0,
            "initiative_level": 2,
            "can_gently_disagree": True,
            "address_user_by_name": False,
            "is_active": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["tone"] == "calm"
    assert updated.json()["initiative_level"] == 2
    assert updated.json()["address_user_by_name"] is False

    created_space = client.post("/api/spaces", json={"name": "Work"})
    assert created_space.status_code == 201
    space_id = created_space.json()["id"]

    overlay_get = client.get(f"/api/personality/overlay/{space_id}")
    assert overlay_get.status_code == 200
    assert overlay_get.json()["scope"] == "space_overlay"
    assert overlay_get.json()["space_id"] == space_id

    overlay_put = client.put(
        f"/api/personality/overlay/{space_id}",
        json={
            "name": "Asya",
            "tone": "strict",
            "style_notes": "Только шаги и решения",
            "humor_level": 0,
            "initiative_level": 1,
            "can_gently_disagree": True,
            "address_user_by_name": True,
            "is_active": True,
        },
    )
    assert overlay_put.status_code == 200
    assert overlay_put.json()["tone"] == "strict"

    base_after = client.get("/api/personality")
    assert base_after.status_code == 200
    assert base_after.json()["tone"] == "calm"
    app.dependency_overrides.clear()


def test_activity_log_supports_filters_and_snapshot_events(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)

    client = TestClient(app)
    _register_and_login(client, "activity-filters@example.com", "Activity")

    fact = client.post(
        "/api/memory/facts",
        json={"key": "lang", "value": "ru", "status": "confirmed", "source": "user"},
    )
    assert fact.status_code == 200

    snapshot = client.post("/api/memory/snapshots", json={"label": "manual snapshot"})
    assert snapshot.status_code == 200

    by_event = client.get("/api/activity-log", params={"event_type": "memory_snapshot_created"})
    assert by_event.status_code == 200
    assert all(item["event_type"] == "memory_snapshot_created" for item in by_event.json())

    by_entity = client.get("/api/activity-log", params={"entity_type": "memory_snapshot"})
    assert by_entity.status_code == 200
    assert by_entity.json()
    assert all(item["entity_type"] == "memory_snapshot" for item in by_entity.json())

    bad_date = client.get("/api/activity-log", params={"date_from": "not-a-date"})
    assert bad_date.status_code == 400

    snapshots = client.get("/api/memory/snapshots")
    assert snapshots.status_code == 200
    assert any(item["id"] == snapshot.json()["id"] for item in snapshots.json())
    app.dependency_overrides.clear()


def test_snapshot_summary_and_rollback_restore_memory_state(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client = TestClient(app)
    _register_and_login(client, "rollback@example.com", "Rollback")

    fact = client.post(
        "/api/memory/facts",
        json={"key": "tone", "value": "calm", "status": "confirmed", "source": "user"},
    )
    assert fact.status_code == 200
    fact_id = fact.json()["id"]

    rule = client.post(
        "/api/memory/rules",
        json={
            "title": "Brief",
            "instruction": "Пиши кратко",
            "scope": "user",
            "strictness": "normal",
            "source": "user",
            "status": "active",
        },
    )
    assert rule.status_code == 200
    rule_id = rule.json()["id"]

    snapshot = client.post("/api/memory/snapshots", json={"label": "before-change"})
    assert snapshot.status_code == 200
    snapshot_id = snapshot.json()["id"]

    update_fact = client.patch(
        f"/api/memory/facts/{fact_id}",
        json={"key": "tone", "value": "strict", "source": "assistant"},
    )
    assert update_fact.status_code == 200

    update_rule = client.patch(
        f"/api/memory/rules/{rule_id}",
        json={
            "title": "Brief",
            "instruction": "Пиши очень подробно",
            "scope": "user",
            "strictness": "normal",
            "source": "assistant",
            "status": "active",
        },
    )
    assert update_rule.status_code == 200

    summary = client.get(f"/api/memory/snapshots/{snapshot_id}")
    assert summary.status_code == 200
    assert summary.json()["facts_count"] >= 1
    assert summary.json()["rules_count"] >= 1

    rollback = client.post(f"/api/memory/snapshots/{snapshot_id}/rollback")
    assert rollback.status_code == 200

    facts_after = client.get("/api/memory/facts", params={"active_only": "false"})
    assert facts_after.status_code == 200
    restored_fact = next(item for item in facts_after.json() if item["id"] == fact_id)
    assert restored_fact["value"] == "calm"

    rules_after = client.get("/api/memory/rules")
    assert rules_after.status_code == 200
    restored_rule = next(item for item in rules_after.json() if item["id"] == rule_id)
    assert restored_rule["instruction"] == "Пиши кратко"

    activity = client.get("/api/activity-log", params={"event_type": "memory_rollback"})
    assert activity.status_code == 200
    assert any(item["entity_id"] == snapshot_id for item in activity.json())

    changes = client.get("/api/memory/changes")
    assert changes.status_code == 200
    assert any(item["change_kind"] == "rollback" and item["entity_id"] == snapshot_id for item in changes.json())
    app.dependency_overrides.clear()


def test_snapshot_and_rollback_are_user_scoped(tmp_path, monkeypatch) -> None:
    engine = _setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = _override_db_session(engine)
    client_a = TestClient(app)
    client_b = TestClient(app)
    _register_and_login(client_a, "snap-a@example.com", "A")
    _register_and_login(client_b, "snap-b@example.com", "B")

    snap = client_a.post("/api/memory/snapshots", json={"label": "a-only"})
    assert snap.status_code == 200
    snapshot_id = snap.json()["id"]

    summary_by_b = client_b.get(f"/api/memory/snapshots/{snapshot_id}")
    assert summary_by_b.status_code == 404

    rollback_by_b = client_b.post(f"/api/memory/snapshots/{snapshot_id}/rollback")
    assert rollback_by_b.status_code == 404
    app.dependency_overrides.clear()
