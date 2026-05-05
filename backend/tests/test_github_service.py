from __future__ import annotations

from app.integrations.github import GitHubService


def test_github_service_has_only_read_methods() -> None:
    forbidden = [
        "create_repository",
        "update_repository",
        "delete_repository",
        "create_issue",
        "update_issue",
        "create_pull_request",
        "merge_pull_request",
        "create_comment",
        "create_review",
    ]
    for method_name in forbidden:
        assert not hasattr(GitHubService, method_name)
