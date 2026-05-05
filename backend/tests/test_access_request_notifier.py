from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.access_request_notifier import DevLogAccessRequestNotifier


def test_on_approved_does_not_log_setup_link_or_token() -> None:
    notifier = DevLogAccessRequestNotifier()
    request = SimpleNamespace(id="req-123", email="user@example.com")
    user = SimpleNamespace(id="user-456")
    setup_link = "https://example.com/setup-password?token=super-secret-token"

    with patch("app.services.access_request_notifier.logger.info") as logger_info:
        notifier.on_approved(request=request, user=user, setup_link=setup_link)

    logger_info.assert_called_once_with(
        "access_request_approved_notification_sent request_id=%s user_id=%s",
        "req-123",
        "user-456",
    )
    assert setup_link not in repr(logger_info.call_args)
    assert "super-secret-token" not in repr(logger_info.call_args)
