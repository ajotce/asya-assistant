from app.api.deps_auth import get_db_session
from app.main import app
from tests.auth_helpers import build_authed_client


def test_chats_list_contains_base_chat_and_messages_endpoint(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, "chats@example.com", "Chats")

    listed = client.get("/api/chats")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) >= 1
    base = next((item for item in items if item["kind"] == "base"), None)
    assert base is not None

    messages = client.get(f"/api/chats/{base['id']}/messages")
    assert messages.status_code == 200
    assert isinstance(messages.json(), list)
    app.dependency_overrides.clear()


def test_chat_crud_and_base_chat_restrictions(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, "crud@example.com", "Crud")

    created = client.post("/api/chats", json={"title": "Рабочий чат"})
    assert created.status_code == 201
    chat_id = created.json()["id"]

    renamed = client.patch(f"/api/chats/{chat_id}", json={"title": "Переименованный"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Переименованный"

    archived = client.post(f"/api/chats/{chat_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True

    listed = client.get("/api/chats").json()
    base = next(item for item in listed if item["kind"] == "base")
    delete_base = client.delete(f"/api/chats/{base['id']}")
    assert delete_base.status_code == 400

    delete_archived = client.delete(f"/api/chats/{chat_id}")
    assert delete_archived.status_code == 204
    app.dependency_overrides.clear()
