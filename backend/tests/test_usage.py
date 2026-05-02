from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.main import app
from app.repositories.file_meta_repository import FileMetaRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.usage_record_repository import UsageRecordRepository
from app.storage.runtime import vector_store
from app.storage.vector_store import StoredChunkVector
from tests.auth_helpers import override_db_session, setup_test_db


def _authed_client(tmp_path, monkeypatch):
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": "usage@example.com", "display_name": "Usage", "password": "strong-pass-123"},
    )
    client.post("/api/auth/login", json={"email": "usage@example.com", "password": "strong-pass-123"})
    user = client.get("/api/auth/me").json()
    return client, engine, user["id"]


def test_usage_overview_returns_success(tmp_path, monkeypatch) -> None:
    client, _, _ = _authed_client(tmp_path, monkeypatch)
    response = client.get("/api/usage")
    assert response.status_code == 200
    payload = response.json()
    assert "chat" in payload
    assert "embeddings" in payload
    assert "cost" in payload
    assert "runtime" in payload
    assert isinstance(payload["runtime"]["active_sessions"], int)
    app.dependency_overrides.clear()


def test_usage_overview_and_session_payload_shape_with_missing_usage_data(tmp_path, monkeypatch) -> None:
    client, engine, user_id = _authed_client(tmp_path, monkeypatch)
    created = client.post("/api/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    with Session(bind=engine) as db_session:
        msg_repo = MessageRepository(db_session)
        msg_repo.create(chat_id=session_id, user_id=user_id, role="user", content="hello")
        msg_repo.create(chat_id=session_id, user_id=None, role="assistant", content="hi")
        FileMetaRepository(db_session).create(
            file_id="file-1",
            user_id=user_id,
            chat_id=session_id,
            filename="sample.pdf",
            content_type="application/pdf",
            size=10,
            storage_path="/tmp/safe/sample.pdf",
            extracted_text_status="indexed",
            extracted_text_meta=None,
        )
        db_session.commit()

    vector_store.upsert_file_chunks(
        session_id=session_id,
        file_id="file-1",
        chunks=[
            StoredChunkVector(
                chunk_id="chunk-1",
                file_id="file-1",
                filename="sample.pdf",
                text="context",
                embedding=[1.0, 0.0],
            )
        ],
    )

    overview = client.get("/api/usage")
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["chat"]["status"] == "unavailable"
    assert overview_payload["embeddings"]["status"] == "unavailable"

    session_usage = client.get(f"/api/usage/session/{session_id}")
    assert session_usage.status_code == 200
    payload = session_usage.json()
    assert payload["runtime"]["session_id"] == session_id
    assert payload["runtime"]["message_count"] == 2
    assert payload["runtime"]["user_messages"] == 1
    assert payload["runtime"]["assistant_messages"] == 1
    assert payload["runtime"]["file_count"] == 1
    assert payload["runtime"]["chunks_indexed"] == 1

    deleted = client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 204
    app.dependency_overrides.clear()


def test_usage_session_returns_404_for_missing_session(tmp_path, monkeypatch) -> None:
    client, _, _ = _authed_client(tmp_path, monkeypatch)
    response = client.get("/api/usage/session/missing-session-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Сессия не найдена."
    app.dependency_overrides.clear()


def test_usage_overview_returns_available_when_usage_collected(tmp_path, monkeypatch) -> None:
    client, engine, user_id = _authed_client(tmp_path, monkeypatch)
    session_id = client.post("/api/session").json()["session_id"]
    with Session(bind=engine) as db_session:
        repo = UsageRecordRepository(db_session)
        repo.create(
            user_id=user_id,
            chat_id=session_id,
            kind="chat",
            model="openai/gpt-5",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        repo.create(
            user_id=user_id,
            chat_id=session_id,
            kind="embeddings",
            model="text-embedding-3-small",
            prompt_tokens=8,
            completion_tokens=None,
            total_tokens=8,
        )
        db_session.commit()

    overview = client.get("/api/usage")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["chat"]["status"] == "available"
    assert payload["chat"]["prompt_tokens"] == 10
    assert payload["chat"]["completion_tokens"] == 5
    assert payload["chat"]["total_tokens"] == 15
    assert payload["embeddings"]["status"] == "available"
    assert payload["embeddings"]["input_tokens"] == 8
    assert payload["embeddings"]["total_tokens"] == 8
    app.dependency_overrides.clear()


def test_usage_isolation_between_users(tmp_path, monkeypatch) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client_a = TestClient(app)
    client_b = TestClient(app)

    client_a.post(
        "/api/auth/register",
        json={"email": "ua@example.com", "display_name": "UA", "password": "strong-pass-123"},
    )
    client_a.post("/api/auth/login", json={"email": "ua@example.com", "password": "strong-pass-123"})
    session_id = client_a.post("/api/session").json()["session_id"]

    client_b.post(
        "/api/auth/register",
        json={"email": "ub@example.com", "display_name": "UB", "password": "strong-pass-123"},
    )
    client_b.post("/api/auth/login", json={"email": "ub@example.com", "password": "strong-pass-123"})

    response = client_b.get(f"/api/usage/session/{session_id}")
    assert response.status_code == 404
    app.dependency_overrides.clear()
