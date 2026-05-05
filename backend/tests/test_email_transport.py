from __future__ import annotations

from unittest.mock import patch

from app.services.email_transport import MockEmailTransport


def test_mock_email_transport_does_not_log_body() -> None:
    sensitive_body = "secret-token=abc123\npassword=very-secret"

    with patch("app.services.email_transport.logger.info") as logger_info:
        MockEmailTransport().send(
            to_email="user@example.com",
            subject="Access granted",
            text_body=sensitive_body,
        )

    logger_info.assert_called_once_with(
        "mock_email to=%s subject=%s body_len=%d",
        "user@example.com",
        "Access granted",
        len(sensitive_body),
    )

    call_args_repr = repr(logger_info.call_args)
    assert sensitive_body not in call_args_repr
    assert "password=very-secret" not in call_args_repr
    assert "secret-token=abc123" not in call_args_repr
