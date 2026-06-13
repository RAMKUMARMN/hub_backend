"""
Email utility — SMTP sender for OTPs and password reset links.

Person 4 (OTP & Password Recovery) owns this file.
Uses SMTP settings from app.config.settings.

TODO:
  1. send_otp_email(to_email, otp_code) → None
  2. send_password_reset_email(to_email, reset_link) → None

  Use aiosmtplib for async sending:
      async with aiosmtplib.SMTP(hostname=settings.smtp_host, port=settings.smtp_port) as smtp:
          await smtp.send_message(msg)
"""
import logging

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text email.

    TODO (Person 4): implement with aiosmtplib using settings.smtp_*.
    """
    logger.info("[EMAIL STUB] To: %s | Subject: %s", to, subject)
