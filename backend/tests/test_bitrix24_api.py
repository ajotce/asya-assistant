from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import build_authed_client


def test_bitrix24_endpoints_require_auth(tmp_path, monkeypatch) -> None:
    client = TestClient(app)
    assert client.get("/api/integrations/bitrix24/leads").status_code == 401
    assert client.get("/api/integrations/bitrix24/deals").status_code == 401
    assert client.get("/api/integrations/bitrix24/contacts").status_code == 401
    assert client.get("/api/integrations/bitrix24/tasks").status_code == 401
    assert client.get("/api/integrations/bitrix24/calls").status_code == 401
    assert client.get("/api/integrations/bitrix24/pipelines").status_code == 401


def test_bitrix24_readonly_routes_reject_write_methods(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, email="readonly@example.com")

    assert client.post("/api/integrations/bitrix24/leads").status_code == 405
    assert client.patch("/api/integrations/bitrix24/leads/1").status_code == 405
    assert client.delete("/api/integrations/bitrix24/deals/1").status_code == 405


def test_bitrix24_list_leads_is_user_scoped(tmp_path, monkeypatch) -> None:
    client_a = build_authed_client(tmp_path, monkeypatch, email="bitrix-a@example.com")
    client_b = build_authed_client(tmp_path, monkeypatch, email="bitrix-b@example.com")

    def _fake_list_leads(self, *, user_id: str, source_id=None, created_since=None):
        return {"result": [{"id": user_id, "source": source_id or "unknown"}], "total": 1}

    monkeypatch.setattr("app.integrations.bitrix24.Bitrix24Service.list_leads", _fake_list_leads)

    a_resp = client_a.get("/api/integrations/bitrix24/leads?source_id=YANDEX_DIRECT")
    b_resp = client_b.get("/api/integrations/bitrix24/leads?source_id=YANDEX_DIRECT")
    assert a_resp.status_code == 200
    assert b_resp.status_code == 200
    assert a_resp.json()["result"][0]["id"] != b_resp.json()["result"][0]["id"]


def test_bitrix24_date_validation(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, email="bitrix-date@example.com")
    response = client.get("/api/integrations/bitrix24/deals?date_from=2026/01/01")
    assert response.status_code == 400
