"""
Email utility — SMTP sender for OTPs and password reset links.

Person 4 (OTP & Password Recovery) owns this file.
Uses SMTP settings from app.config.settings.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    body: str,
    message_type: str = "general",
    priority: str = "high",
) -> None:
    """
    Send a plain-text email by publishing it to the RabbitMQ priority queue.
    Falls back to logger output if the RabbitMQ service is unavailable.
    """
    from app.queue.producer import publish_notification_to_queue

    html_body = f"<p>{body.replace(chr(10), '<br>')}</p>"

    # Always print notification directly to terminal console for ease of local testing/registration
    print(
        "\n"
        "=================== [DEVELOPMENT NOTIFICATION PRINT] ===================\n"
        f"TO:      {to}\n"
        f"SUBJECT: {subject}\n"
        "BODY:\n"
        f"{body}\n"
        "========================================================\n"
    )

    try:
        await publish_notification_to_queue(
            channel="email",
            recipient=to,
            subject=subject,
            body=body,
            message_type=message_type,
            priority=priority,
            html_body=html_body,
        )
        logger.info(
            "Email notification successfully published to RabbitMQ %s queue for %s: Subject '%s'",
            priority,
            to,
            subject,
        )
    except Exception as e:
        logger.warning(
            "RabbitMQ notification publishing failed. Falling back to log print. Details: %s",
            e,
        )
        logger.info(
            "\n"
            "=================== [NOTIFICATION SERVICE MOCK] ===================\n"
            "TO:      %s\n"
            "SUBJECT: %s\n"
            "BODY:\n"
            "%s\n"
            "========================================================",
            to,
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
    await send_email(to_email, subject, body, message_type="otp", priority="high")


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Send a password reset link via email."""
    subject = f"{settings.app_name} - Password Reset Request"
    body = (
        f"We received a request to reset the password for your account.\n"
        f"Please use the following link to reset your password:\n\n"
        f"{reset_link}\n\n"
        f"This link is valid for 15 minutes. If you did not request this, please ignore this email."
    )
    await send_email(to_email, subject, body, message_type="password_reset", priority="high")

