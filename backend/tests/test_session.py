from pathlib import Path
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.storage.runtime import file_store, vector_store


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


def test_upload_file_to_session_and_cleanup_on_delete() -> None:
    client = TestClient(app)
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
