from __future__ import annotations

import io
import json
import zipfile

import boto3
import httpx
from fastapi.testclient import TestClient
from moto.server import ThreadedMotoServer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.db.models.chat import Chat
from app.db.models.deleted_user_audit import DeletedUserAudit
from app.db.models.diary_entry import DiaryEntry
from app.db.models.encrypted_secret import EncryptedSecret
from app.db.models.message import Message
from app.db.models.user import User
from app.main import app
from app.storage import runtime as storage_runtime
from app.storage.object_storage import S3ObjectStorage
from tests.auth_helpers import override_db_session, setup_test_db


def _register_and_login(client: TestClient, email: str) -> None:
    client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "Export User", "password": "strong-pass-123"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def test_user_export_and_account_deletion_full_cycle(tmp_path, monkeypatch) -> None:
    moto_server = ThreadedMotoServer(port=0)
    moto_server.start()
    host, port = moto_server.get_host_and_port()
    endpoint_url = f"http://{host}:{port}"
    s3_storage = S3ObjectStorage(
        bucket="asya-dev",
        endpoint_url=endpoint_url,
        presign_endpoint_url=endpoint_url,
        region="us-east-1",
        access_key="test",
        secret_key="test",
    )
    boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ).create_bucket(Bucket="asya-dev")
    monkeypatch.setattr(storage_runtime, "blob_storage", s3_storage)
    monkeypatch.setattr("app.services.user_export.blob_storage", s3_storage)
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "s3")

    try:
        _, engine = setup_test_db(tmp_path, monkeypatch)
        app.dependency_overrides[get_db_session] = override_db_session(engine)
        client = TestClient(app)
        _register_and_login(client, "export@example.com")

        with Session(bind=engine) as session:
            user = session.execute(select(User).where(User.email == "export@example.com")).scalar_one()
            chat = session.execute(select(Chat).where(Chat.user_id == user.id)).scalar_one()
            session.add(
                Message(
                    chat_id=chat.id,
                    user_id=user.id,
                    role="user",
                    content="hello export",
                    meta={"kind": "test"},
                )
            )
            session.add(
                EncryptedSecret(
                    user_id=user.id,
                    secret_type="integration_token",
                    name="github_access_token",
                    encrypted_value=b"very-secret-token-value",
                )
            )
            diary = DiaryEntry(
                user_id=user.id,
                title="Voice note",
                content="test diary",
                transcript="test diary",
                topics=[],
                decisions=[],
                mentions=[],
                source_audio_path=f"diary/{user.id}/voice.webm",
                processing_status="processed",
                processing_error=None,
                duration_seconds=3,
                is_deleted=False,
            )
            session.add(diary)
            session.commit()
            s3_storage.put_bytes(f"diary/{user.id}/voice.webm", b"audio-bytes")
            user_id = user.id

        start = client.post("/api/me/export")
        assert start.status_code == 200
        export_id = start.json()["export_id"]

        status = client.get(f"/api/me/export/{export_id}")
        assert status.status_code == 200
        status_payload = status.json()
        assert status_payload["status"] == "ready"
        assert status_payload["download_url"]
        assert "X-Amz-Expires=86400" in status_payload["download_url"]
        assert "X-Amz-Signature" in status_payload["download_url"]

        download = httpx.get(status_payload["download_url"], timeout=10.0)
        assert download.status_code == 200
        assert download.headers["content-type"] in {
            "application/zip",
            "application/octet-stream",
            "binary/octet-stream",
        }

        archive = zipfile.ZipFile(io.BytesIO(download.content))
        names = archive.namelist()
        assert "export.json" in names
        assert any(name.startswith("diary_audio/") for name in names)

        export_json = json.loads(archive.read("export.json").decode("utf-8"))
        assert "integrations" in export_json
        assert "encrypted_secrets" not in export_json

        archive_text = download.content.decode("latin-1").lower()
        assert "very-secret-token-value" not in archive_text
        assert "access_token" not in archive_text
        assert "refresh_token" not in archive_text

        confirm = client.delete("/api/me")
        assert confirm.status_code == 200
        confirmation_token = confirm.json()["confirmation_token"]

        delete_resp = client.delete(
            f"/api/me?confirmation_token={confirmation_token}&password=strong-pass-123"
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"

        with Session(bind=engine) as session:
            messages_count = session.execute(
                select(func.count()).select_from(Message).where(Message.user_id == user_id)
            ).scalar_one()
            assert messages_count == 0
            user_exists = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            assert user_exists is None
            secret_count = session.execute(
                select(func.count()).select_from(EncryptedSecret).where(EncryptedSecret.user_id == user_id)
            ).scalar_one()
            assert secret_count == 0
            audit = session.execute(
                select(DeletedUserAudit).where(DeletedUserAudit.deleted_user_id == user_id)
            ).scalar_one_or_none()
            assert audit is not None
    finally:
        app.dependency_overrides.clear()
        moto_server.stop()
