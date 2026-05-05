from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.common import UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.services.action_router import ActionRouter


def _router_with_user():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    user = UserRepository(session).create(
        email="githubuser@example.com",
        display_name="Github User",
        password_hash="hash",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return ActionRouter(session=session, pending_store={}), user.id


def test_tool_github_open_issues(monkeypatch) -> None:
    router, user_id = _router_with_user()

    def _fake_list_issues(self, *, user, owner, repo, state="open", per_page=30):
        return [{"number": 1, "title": "Issue 1"}, {"number": 2, "title": "Issue 2"}]

    monkeypatch.setattr("app.integrations.github.GitHubService.list_issues", _fake_list_issues)
    result = router.handle(
        user_id=user_id,
        session_id="s1",
        message="покажи открытые issues в репозитории octo/test",
    )
    assert result.handled is True
    assert "Issue 1" in result.message


def test_tool_github_read_file(monkeypatch) -> None:
    router, user_id = _router_with_user()

    def _fake_read_file(self, *, user, owner, repo, path, ref=None):
        return {"content": "SGVsbG8=", "encoding": "base64"}

    monkeypatch.setattr("app.integrations.github.GitHubService.read_file", _fake_read_file)
    result = router.handle(
        user_id=user_id,
        session_id="s1",
        message="прочитай файл README.md в репозитории octo/test",
    )
    assert result.handled is True
    assert "Hello" in result.message
