from __future__ import annotations

import time
import zipfile

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps_auth import get_db_session
from app.db.models.activity_log import ActivityLog
from app.db.models.assistant_personality_profile import AssistantPersonalityProfile
from app.db.models.behavior_rule import BehaviorRule
from app.db.models.chat import Chat
from app.db.models.deleted_user_audit import DeletedUserAudit
from app.db.models.diary_entry import DiaryEntry
from app.db.models.file_meta import FileMeta
from app.db.models.integration_connection import IntegrationConnection
from app.db.models.memory_episode import MemoryEpisode
from app.db.models.message import Message
from app.db.models.observation import Observation
from app.db.models.space import Space
from app.db.models.space_memory_settings import SpaceMemorySettings
from app.db.models.user_export import UserExport
from app.main import app
from tests.auth_helpers import override_db_session, setup_test_db
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "Export User", "password": "strong-pass-123"},
    )
    assert reg.status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "strong-pass-123"})
    assert login.status_code == 200


def test_export_and_delete_account_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EXPORT_DIR", (tmp_path / "exports").as_posix())
    monkeypatch.setenv("DIARY_AUDIO_DIR", (tmp_path / "diary_audio").as_posix())
    settings, engine = setup_test_db(tmp_path, monkeypatch)
    app.dependency_overrides[get_db_session] = override_db_session(engine)
    client = TestClient(app)

    _register_and_login(client, "export-delete@example.com")
    user = client.get("/api/auth/me").json()
    user_id = user["id"]

    chat = client.post("/api/chats", json={"title": "Export Chat"}).json()
    chat_id = chat["id"]

    with Session(bind=engine) as db:
        db.add(
            Message(
                chat_id=chat_id,
                user_id=user_id,
                role="user",
                content="hello export",
            )
        )
        db.add(DiaryEntry(user_id=user_id, title="D", content="diary", transcript="audio text", topics=[], decisions=[], mentions=[]))
        db.add(BehaviorRule(user_id=user_id, title="Rule", instruction="Do", scope="user", strictness="normal", source="user", status="active"))
        db.add(AssistantPersonalityProfile(user_id=user_id, scope="base", name="Asya", tone="neutral", style_notes="", humor_level=1, initiative_level=1, can_gently_disagree=True, address_user_by_name=True, is_active=True))
        db.add(
            FileMeta(
                user_id=user_id,
                filename="template.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size=10,
                storage_path="/tmp/template.docx",
            )
        )
        db.commit()

    start_resp = client.post("/api/me/export")
    assert start_resp.status_code == 200
    export_id = start_resp.json()["export_id"]

    status_payload = None
    for _ in range(20):
        status = client.get(f"/api/me/export/{export_id}")
        assert status.status_code == 200
        status_payload = status.json()
        if status_payload["status"] == "ready":
            break
        time.sleep(0.1)
    assert status_payload is not None
    assert status_payload["status"] == "ready"
    assert status_payload["download_url"]

    download_url = status_payload["download_url"]
    download = client.get(download_url)
    assert download.status_code == 200
    archive_path = tmp_path / "downloaded.zip"
    archive_path.write_bytes(download.content)

    second_download = client.get(download_url)
    assert second_download.status_code == 404

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        assert "profile.json" in names
        assert all("encrypted_secret" not in name for name in names)
        all_text = "\n".join(archive.read(name).decode("utf-8", errors="ignore") for name in names if name.endswith(".json"))
        assert "oauth_tokens" not in all_text
        assert "encrypted_secrets" not in all_text

    prepare_delete = client.request("DELETE", "/api/me", json={"password": "strong-pass-123"})
    assert prepare_delete.status_code == 200
    confirmation_token = prepare_delete.json()["confirmation_token"]

    confirm_delete = client.delete(f"/api/me/confirm?token={confirmation_token}")
    assert confirm_delete.status_code == 200
    assert confirm_delete.json()["status"] == "deleted"

    unauthorized = client.get("/api/auth/me")
    assert unauthorized.status_code == 401

    with Session(bind=engine) as db:
        for model in (
            Chat,
            Message,
            DiaryEntry,
            BehaviorRule,
            AssistantPersonalityProfile,
            Observation,
            FileMeta,
            MemoryEpisode,
            Space,
            SpaceMemorySettings,
            ActivityLog,
            IntegrationConnection,
            UserExport,
        ):
            count = db.execute(select(func.count()).select_from(model).where(model.user_id == user_id)).scalar_one()
            assert count == 0

        audit_count = db.execute(select(func.count()).select_from(DeletedUserAudit).where(DeletedUserAudit.user_id == user_id)).scalar_one()
        assert audit_count == 1
