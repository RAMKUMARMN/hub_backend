from app.services.email_service import send_email


async def send_deadline_reminder_email(
    email: str,
    todo_title: str,
):
    await send_email(
        to_email=email,
        subject="Todo Deadline Reminder",
        body=(
            f"Reminder: Your todo "
            f"'{todo_title}' is due soon."
        ),
    )