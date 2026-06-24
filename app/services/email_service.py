import aiosmtplib
from email.message import EmailMessage

from app.config import settings


async def send_email(
    to_email: str,
    subject: str,
    body: str,
):
    message = EmailMessage()

    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,  # REQUIRED for Gmail (587)
        )

        print("EMAIL SENT →", to_email)

    except Exception as e:
        print("EMAIL ERROR:", str(e))
        raise e