"""
Email utility — SMTP sender for OTPs and password reset links.

Person 4 (OTP & Password Recovery) owns this file.
Uses SMTP settings from app.config.settings.
"""
import logging
from email.message import EmailMessage
import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text email using SMTP.
    Falls back to logger output if the SMTP connection is refused (common in dev/test).
    """
    msg = EmailMessage()
    msg["From"] = settings.smtp_from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        async with aiosmtplib.SMTP(hostname=settings.smtp_host, port=settings.smtp_port) as smtp:
            await smtp.send_message(msg)
        logger.info("Email sent successfully to %s: Subject '%s'", to, subject)
    except Exception as e:
        logger.warning(
            "SMTP transmission failed. Falling back to log print. Details: %s", e
        )
        logger.info(
            "\n"
            "=================== [EMAIL LOG MOCK] ===================\n"
            "TO:      %s\n"
            "FROM:    %s\n"
            "SUBJECT: %s\n"
            "BODY:\n"
            "%s\n"
            "========================================================",
            to,
            settings.smtp_from_email,
            subject,
            body,
        )


async def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send a verification OTP code via email."""
    subject = f"{settings.app_name} - Email Verification Code"
    body = (
        f"Your verification code is: {otp_code}\n\n"
        f"This code is valid for 10 minutes. Please do not share it with anyone."
    )
    await send_email(to_email, subject, body)


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Send a password reset link via email."""
    subject = f"{settings.app_name} - Password Reset Request"
    body = (
        f"We received a request to reset the password for your account.\n"
        f"Please use the following link to reset your password:\n\n"
        f"{reset_link}\n\n"
        f"This link is valid for 15 minutes. If you did not request this, please ignore this email."
    )
    await send_email(to_email, subject, body)
