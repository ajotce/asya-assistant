from __future__ import annotations

from app.api import routes_integrations
from tests.auth_helpers import build_authed_client


def test_bitrix24_leads_returns_409_when_module_unavailable(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, email="bitrix-leads@example.com")
    monkeypatch.setattr(routes_integrations, "Bitrix24Service", None)

    response = client.get("/api/integrations/bitrix24/leads")
    assert response.status_code == 409
    assert response.json()["detail"] == "Bitrix24 integration is not available in this build."


def test_bitrix24_pipelines_returns_409_when_module_unavailable(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, email="bitrix-pipelines@example.com")
    monkeypatch.setattr(routes_integrations, "Bitrix24Service", None)

    response = client.get("/api/integrations/bitrix24/pipelines")
    assert response.status_code == 409
    assert response.json()["detail"] == "Bitrix24 integration is not available in this build."
