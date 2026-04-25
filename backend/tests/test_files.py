from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _create_session(client: TestClient) -> str:
    response = client.post("/api/session")
    assert response.status_code == 201
    return response.json()["session_id"]


def test_upload_rejects_more_than_max_files_per_message() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    files = [("files", (f"f{i}.pdf", b"%PDF-1.7", "application/pdf")) for i in range(11)]
    response = client.post(f"/api/session/{session_id}/files", files=files)

    assert response.status_code == 400
    assert "не более 10 файлов" in response.json()["detail"]


def test_upload_rejects_unsupported_file_type() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        f"/api/session/{session_id}/files",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 400
    assert "не поддерживается" in response.json()["detail"]


def test_upload_rejects_file_over_size_limit() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    settings = get_settings()
    old_limit = settings.max_file_size_mb
    settings.max_file_size_mb = 1
    try:
        oversized = b"x" * (1024 * 1024 + 1)
        response = client.post(
            f"/api/session/{session_id}/files",
            files=[("files", ("big.pdf", oversized, "application/pdf"))],
        )
    finally:
        settings.max_file_size_mb = old_limit

    assert response.status_code == 400
    assert "превышает лимит 1 МБ" in response.json()["detail"]
