from fastapi.testclient import TestClient

from app.main import app
from app.storage.runtime import session_store, usage_store, vector_store
from app.storage.vector_store import StoredChunkVector


def test_usage_overview_returns_success() -> None:
    usage_store.reset()
    client = TestClient(app)
    response = client.get("/api/usage")
    assert response.status_code == 200
    payload = response.json()

    assert "chat" in payload
    assert "embeddings" in payload
    assert "cost" in payload
    assert "runtime" in payload
    assert isinstance(payload["runtime"]["active_sessions"], int)


def test_usage_overview_and_session_payload_shape_with_missing_usage_data() -> None:
    usage_store.reset()
    client = TestClient(app)
    created = client.post("/api/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    # Prepare basic runtime state for session usage response.
    session_store.append_message(session_id, "user", "hello")
    session_store.append_message(session_id, "assistant", "hi")
    session_store.bind_file(session_id, "file-1")
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
    assert overview_payload["chat"]["prompt_tokens"] is None
    assert overview_payload["embeddings"]["status"] == "unavailable"
    assert overview_payload["embeddings"]["input_tokens"] is None
    assert overview_payload["cost"]["status"] == "unavailable"
    assert overview_payload["cost"]["total_cost"] is None

    session_usage = client.get(f"/api/usage/session/{session_id}")
    assert session_usage.status_code == 200
    payload = session_usage.json()
    assert payload["runtime"]["session_id"] == session_id
    assert payload["runtime"]["message_count"] == 2
    assert payload["runtime"]["user_messages"] == 1
    assert payload["runtime"]["assistant_messages"] == 1
    assert payload["runtime"]["file_count"] == 1
    assert payload["runtime"]["chunks_indexed"] == 1
    assert payload["chat"]["total_tokens"] is None
    assert payload["embeddings"]["total_tokens"] is None
    assert payload["cost"]["total_cost"] is None

    deleted = client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 204


def test_usage_session_returns_404_for_missing_session() -> None:
    usage_store.reset()
    client = TestClient(app)
    response = client.get("/api/usage/session/missing-session-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Сессия не найдена."


def test_usage_overview_returns_available_when_usage_collected() -> None:
    usage_store.reset()
    client = TestClient(app)
    session_id = client.post("/api/session").json()["session_id"]

    usage_store.record_chat_usage(
        session_id=session_id,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    usage_store.record_embeddings_usage(
        session_id=session_id,
        usage={"prompt_tokens": 8, "total_tokens": 8},
    )

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
