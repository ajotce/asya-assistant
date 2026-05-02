from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmailTransport:
    def send(self, *, to_email: str, subject: str, text_body: str) -> None:
        raise NotImplementedError


class MockEmailTransport(EmailTransport):
    def send(self, *, to_email: str, subject: str, text_body: str) -> None:
        logger.info("mock_email to=%s subject=%s body=%s", to_email, subject, text_body)


class SmtpEmailTransport(EmailTransport):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, *, to_email: str, subject: str, text_body: str) -> None:
        message = EmailMessage()
        message["From"] = self._settings.email_from
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)

        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=15) as smtp:
            if self._settings.smtp_use_tls:
                smtp.starttls()
            if self._settings.smtp_username:
                smtp.login(self._settings.smtp_username, self._settings.smtp_password)
            smtp.send_message(message)


def get_email_transport(settings: Settings) -> EmailTransport:
    if settings.email_transport.lower() == "smtp":
        return SmtpEmailTransport(settings)
    return MockEmailTransport()
