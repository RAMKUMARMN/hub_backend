from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo
from app.models.user import User
from app.models.user_notification import UserNotification
from app.queue.producer import publish_notification
from app.queue.schemas import NotifyPayload

TODO_DUE_SOON = "TODO_DUE_SOON"


async def create_due_soon_notifications(
    db: AsyncSession,
    manager,
) -> None:
    """
    Runs every minute.

    Sends:
    1. In-app notification
    2. WebSocket notification
    3. Email notification
    """

    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=24)

    print("================================")
    print("Checking due soon todos...")
    print("Current UTC:", now)
    print("Checking until:", soon)
    print("================================")

    result = await db.execute(
        select(Todo, User)
        .join(User, User.id == Todo.user_id)
        .where(
            Todo.completed.is_(False),
            Todo.due_date.is_not(None),
            Todo.due_date >= now,
            Todo.due_date <= soon,
        )
    )

    rows = result.all()

    print(f"Found {len(rows)} todos")

    for todo, user in rows:

        print(f"Processing todo: {todo.title}")

        # Skip if reminder already sent
        if todo.reminder_sent:
            print("Reminder already sent")
            continue

        # Skip if no reminder time
        if not todo.reminder_at:
            print("No reminder_at configured")
            continue

        # Skip until reminder time arrives
        if todo.reminder_at > now:
            print("Reminder time not reached yet")
            continue

        title = "Deadline Approaching"
        message = f'Your task "{todo.title}" is due soon.'

        db.add(
            UserNotification(
                user_id=todo.user_id,
                todo_id=todo.id,
                title=title,
                message=message,
                notification_type=TODO_DUE_SOON,
            )
        )

        # -------------------------
        # WebSocket notification
        # -------------------------
        try:
            print("Sending websocket reminder...")

            await manager.send_notification(
                str(todo.user_id),
                {
                    "type": TODO_DUE_SOON,
                    "title": title,
                    "message": message,
                    "todo_id": str(todo.id),
                    "priority": todo.priority,
                    "due_date": (
                        todo.due_date.isoformat()
                        if todo.due_date
                        else None
                    ),
                },
            )

        except Exception as e:
            print(f"WebSocket failed: {e}")

        # -------------------------
        # Queue email
        # -------------------------
        try:
            print("Queueing email reminder...")

            await publish_notification(
                NotifyPayload(
                    channel="email",
                    recipient=user.email,
                    subject=f"Reminder: {todo.title} is due soon",
                    body=(
                        f"Reminder\n\n"
                        f"Your task '{todo.title}' is due soon.\n\n"
                        f"Priority: {todo.priority}\n"
                        f"Due Date: {todo.due_date}"
                    ),
                    data={
                        "todo_id": str(todo.id),
                        "type": TODO_DUE_SOON,
                    },
                )
            )
            print("✅ Published email reminder to RabbitMQ")

        except Exception as e:
            print(f"Could not queue email reminder: {e}")

        # Mark reminder as sent
        todo.reminder_sent = True

    await db.commit()