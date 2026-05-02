from pathlib import Path
import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.db.models.common import MessageRole
from app.main import app
from app.repositories.message_repository import MessageRepository
from app.storage.runtime import file_store, vector_store
from tests.auth_helpers import override_db_session, setup_test_db


def test_session_create_and_read_and_delete(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "session1@example.com", "display_name": "Session1", "password": "strong-pass-123"},
    )
    client.post("/api/auth/login", json={"email": "session1@example.com", "password": "strong-pass-123"})

    create_resp = client.post("/api/session")
    assert create_resp.status_code == 201
    created = create_resp.json()
    session_id = created["session_id"]
    assert session_id
    assert "created_at" in created

    get_resp = client.get(f"/api/session/{session_id}")
    assert get_resp.status_code == 200
    state = get_resp.json()
    assert state["session_id"] == session_id
    assert state["message_count"] == 0
    assert state["file_ids"] == []

    delete_resp = client.delete(f"/api/session/{session_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/api/session/{session_id}")
    assert missing_resp.status_code == 404
    app.dependency_overrides.clear()


def test_upload_file_to_session_and_cleanup_on_delete(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "session@example.com", "display_name": "Session", "password": "strong-pass-123"},
    )
    client.post("/api/auth/login", json={"email": "session@example.com", "password": "strong-pass-123"})
    session_id = client.post("/api/session").json()["session_id"]
    image = Image.new("RGB", (2, 2), color=(0, 255, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    valid_png = out.getvalue()

    upload_resp = client.post(
        f"/api/session/{session_id}/files",
        files=[("files", ("sample.png", valid_png, "image/png"))],
    )
    assert upload_resp.status_code == 201
    payload = upload_resp.json()
    assert payload["session_id"] == session_id
    assert len(payload["files"]) == 1
    file_id = payload["files"][0]["file_id"]
    assert payload["file_ids"] == [file_id]

    stored = file_store.get_session_files(session_id)
    assert len(stored) == 1
    saved_path = Path(stored[0].path)
    assert saved_path.exists()

    delete_resp = client.delete(f"/api/session/{session_id}")
    assert delete_resp.status_code == 204
    assert not saved_path.exists()
    assert vector_store.search(session_id=session_id, query_embedding=[1.0, 0.0]) == []
    app.dependency_overrides.clear()


def test_session_isolation_between_users(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client_a = TestClient(app)
    client_b = TestClient(app)

    client_a.post(
        "/api/auth/register",
        json={"email": "a@example.com", "display_name": "A", "password": "strong-pass-123"},
    )
    client_a.post("/api/auth/login", json={"email": "a@example.com", "password": "strong-pass-123"})

    client_b.post(
        "/api/auth/register",
        json={"email": "b@example.com", "display_name": "B", "password": "strong-pass-123"},
    )
    client_b.post("/api/auth/login", json={"email": "b@example.com", "password": "strong-pass-123"})

    session_id = client_a.post("/api/session").json()["session_id"]
    read_by_b = client_b.get(f"/api/session/{session_id}")
    assert read_by_b.status_code == 404
    delete_by_b = client_b.delete(f"/api/session/{session_id}")
    assert delete_by_b.status_code == 404
    app.dependency_overrides.clear()


def test_chat_history_persists_after_backend_restart(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)

    client_before_restart = TestClient(app)
    client_before_restart.post(
        "/api/auth/register",
        json={"email": "persist@example.com", "display_name": "Persist", "password": "strong-pass-123"},
    )
    client_before_restart.post("/api/auth/login", json={"email": "persist@example.com", "password": "strong-pass-123"})
    chat_id = client_before_restart.post("/api/session").json()["session_id"]
    with Session(bind=engine) as db_session:
        MessageRepository(db_session).create(
            chat_id=chat_id,
            user_id=None,
            role=MessageRole.ASSISTANT.value,
            content="saved before restart",
        )
        db_session.commit()

    # Эмуляция restart: новый клиент (новый app lifecycle) с тем же sqlite-файлом.
    client_after_restart = TestClient(app)
    client_after_restart.post("/api/auth/login", json={"email": "persist@example.com", "password": "strong-pass-123"})
    state = client_after_restart.get(f"/api/session/{chat_id}")
    assert state.status_code == 200
    assert state.json()["message_count"] == 1

    messages = client_after_restart.get(f"/api/chats/{chat_id}/messages")
    assert messages.status_code == 200
    assert len(messages.json()) == 1
    assert messages.json()[0]["content"] == "saved before restart"
    app.dependency_overrides.clear()
