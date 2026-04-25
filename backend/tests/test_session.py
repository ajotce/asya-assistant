from fastapi.testclient import TestClient

from app.main import app


def test_session_create_and_read_and_delete() -> None:
    client = TestClient(app)

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


def test_bind_file_to_session() -> None:
    client = TestClient(app)
    session_id = client.post("/api/session").json()["session_id"]

    bind_resp = client.post(f"/api/session/{session_id}/files", json={"file_id": "file-123"})
    assert bind_resp.status_code == 200
    payload = bind_resp.json()
    assert payload["session_id"] == session_id
    assert payload["file_ids"] == ["file-123"]
