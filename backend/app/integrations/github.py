from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider, UserRole
from app.db.models.user import User
from app.integrations.oauth_service import OAuthIntegrationService
from app.observability.metrics import observe_integration_api_call
from app.services.integration_connection_service import IntegrationConnectionService


class GitHubNotConnectedError(RuntimeError):
    pass


class GitHubAccessDeniedError(RuntimeError):
    pass


class GitHubAPIError(RuntimeError):
    pass


@dataclass
class GitHubRepoRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


class GitHubService:
    _ASYA_REPO = "ajotce/asya-assistant"

    def __init__(self, session: Session) -> None:
        self._session = session
        self._oauth = OAuthIntegrationService(session)
        self._connections = IntegrationConnectionService(session)
        self._settings = get_settings()

    def status(self, *, user: User) -> dict[str, Any]:
        item = self._connections.get_connection_or_default(user=user, provider=IntegrationProvider.GITHUB)
        return {
            "provider": item.provider.value,
            "status": item.status.value,
            "scopes": item.scopes or [],
            "connected_at": item.connected_at.isoformat() if item.connected_at else None,
            "last_refresh_at": item.last_refresh_at.isoformat() if item.last_refresh_at else None,
            "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
            "safe_error_metadata": item.safe_error_metadata,
        }

    def list_repositories(self, *, user: User, visibility: str | None = None, per_page: int = 30) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"per_page": max(1, min(per_page, 100))}
        if visibility:
            params["visibility"] = visibility
        return self._get(user=user, path="/user/repos", params=params)

    def get_repository(self, *, user: User, owner: str, repo: str) -> dict[str, Any]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        return self._get(user=user, path=f"/repos/{owner}/{repo}")

    def list_issues(
        self,
        *,
        user: User,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        params = {"state": state, "per_page": max(1, min(per_page, 100))}
        return self._get(user=user, path=f"/repos/{owner}/{repo}/issues", params=params)

    def get_issue(self, *, user: User, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        return self._get(user=user, path=f"/repos/{owner}/{repo}/issues/{issue_number}")

    def list_pull_requests(
        self,
        *,
        user: User,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        params = {"state": state, "per_page": max(1, min(per_page, 100))}
        return self._get(user=user, path=f"/repos/{owner}/{repo}/pulls", params=params)

    def get_pull_request(self, *, user: User, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        return self._get(user=user, path=f"/repos/{owner}/{repo}/pulls/{pull_number}")

    def list_commits(
        self,
        *,
        user: User,
        owner: str,
        repo: str,
        sha: str | None = None,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        params: dict[str, Any] = {"per_page": max(1, min(per_page, 100))}
        if sha:
            params["sha"] = sha
        return self._get(user=user, path=f"/repos/{owner}/{repo}/commits", params=params)

    def read_file(self, *, user: User, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
        self._validate_repo_access(user=user, owner=owner, repo=repo)
        params: dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        safe_path = quote(path.strip("/"), safe="/._-")
        return self._get(user=user, path=f"/repos/{owner}/{repo}/contents/{safe_path}", params=params)

    def search_code(self, *, user: User, query: str, owner: str | None = None, repo: str | None = None) -> dict[str, Any]:
        if not query.strip():
            return {"total_count": 0, "incomplete_results": False, "items": []}
        q = query.strip()
        if owner and repo:
            self._validate_repo_access(user=user, owner=owner, repo=repo)
            q = f"{q} repo:{owner}/{repo}"
        return self._get(user=user, path="/search/code", params={"q": q, "per_page": 20})

    def search_mentions_in_issues_and_prs(self, *, user: User, login: str) -> dict[str, Any]:
        q = f"mentions:{login} is:open is:issue"
        return self._get(user=user, path="/search/issues", params={"q": q, "per_page": 20})

    def _get(self, *, user: User, path: str, params: dict[str, Any] | None = None) -> Any:
        token = self._token_for_user(user)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "asya-assistant",
        }
        url = f"{self._settings.github_api_base_url.rstrip('/')}{path}"
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=20.0)
        except httpx.HTTPError as exc:
            observe_integration_api_call(IntegrationProvider.GITHUB.value, "rest_get", False)
            raise GitHubAPIError("Ошибка сети при запросе к GitHub API.") from exc
        observe_integration_api_call(
            IntegrationProvider.GITHUB.value,
            "rest_get",
            response.status_code < 400,
        )
        if response.status_code == 401:
            raise GitHubNotConnectedError("GitHub токен недействителен или отозван.")
        if response.status_code == 403:
            raise GitHubAccessDeniedError("Недостаточно прав токена GitHub для этого чтения.")
        if response.status_code == 404:
            raise GitHubAccessDeniedError("Репозиторий или ресурс не найден, либо нет доступа.")
        if response.status_code >= 400:
            raise GitHubAPIError(f"GitHub API вернул ошибку {response.status_code}.")
        self._connections.mark_synced(user=user, provider=IntegrationProvider.GITHUB)
        return response.json()

    def _token_for_user(self, user: User) -> str:
        try:
            client = self._oauth.get_authenticated_client(provider=IntegrationProvider.GITHUB, user_id=user.id)
        except Exception as exc:  # noqa: BLE001
            raise GitHubNotConnectedError("GitHub интеграция не подключена.") from exc
        return client.access_token

    def _validate_repo_access(self, *, user: User, owner: str, repo: str) -> None:
        full_name = f"{owner}/{repo}".lower()
        if full_name == self._ASYA_REPO and user.role != UserRole.ADMIN:
            raise GitHubAccessDeniedError("Репозиторий Asya доступен только admin-пользователю.")
