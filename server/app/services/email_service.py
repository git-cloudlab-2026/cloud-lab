import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.email_notifications_enabled
            and self.settings.smtp_host
            and self.settings.smtp_from_email
        )

    async def send(self, to_email: str, subject: str, body: str) -> bool:
        if not self.enabled:
            logger.info("Email notification skipped because SMTP is not configured: %s", subject)
            return False

        try:
            await asyncio.to_thread(self._send_sync, to_email, subject, body)
            return True
        except Exception:
            logger.exception("Email notification failed: %s -> %s", subject, to_email)
            return False

    def _send_sync(self, to_email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
