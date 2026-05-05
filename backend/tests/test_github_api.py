from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import build_authed_client


def test_github_endpoints_require_auth() -> None:
    client = TestClient(app)
    assert client.get("/api/integrations/github/status").status_code == 401
    assert client.get("/api/integrations/github/repos").status_code == 401
    assert client.get("/api/integrations/github/repos/owner/repo/issues").status_code == 401
    assert client.get("/api/integrations/github/repos/owner/repo/pulls").status_code == 401
    assert client.get("/api/integrations/github/repos/owner/repo/files?path=README.md").status_code == 401


def test_github_readonly_routes_reject_write_methods(tmp_path, monkeypatch) -> None:
    client = build_authed_client(tmp_path, monkeypatch, email="github-readonly@example.com")
    assert client.post("/api/integrations/github/repos").status_code == 405
    assert client.patch("/api/integrations/github/repos/owner/repo/issues").status_code == 405
    assert client.delete("/api/integrations/github/repos/owner/repo/pulls").status_code == 405


def test_github_repos_endpoint_is_user_scoped(tmp_path, monkeypatch) -> None:
    client_a = build_authed_client(tmp_path, monkeypatch, email="github-a@example.com")
    client_b = build_authed_client(tmp_path, monkeypatch, email="github-b@example.com")

    def _fake_list_repositories(self, *, user, visibility=None, per_page=30):
        return [{"id": user.id, "name": f"repo-{user.id[:6]}"}]

    monkeypatch.setattr("app.integrations.github.GitHubService.list_repositories", _fake_list_repositories)

    a_resp = client_a.get("/api/integrations/github/repos")
    b_resp = client_b.get("/api/integrations/github/repos")
    assert a_resp.status_code == 200
    assert b_resp.status_code == 200
    assert a_resp.json()[0]["id"] != b_resp.json()[0]["id"]
