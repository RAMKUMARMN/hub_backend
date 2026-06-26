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
    Runs every 5 minutes.

    Creates:
    1. In-app notification
    2. WebSocket notification
    3. Email notification queued through RabbitMQ
    """

    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=24)

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

    for todo, user in rows:

        existing = await db.execute(
            select(UserNotification.id).where(
                UserNotification.todo_id == todo.id,
                UserNotification.notification_type == TODO_DUE_SOON,
            )
        )

        if existing.scalar_one_or_none():
            continue

        title = "Deadline Approaching"
        message = f'Your task "{todo.title}" is due within 24 hours.'

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
        # Queue Email
        # -------------------------
        try:
            await publish_notification(
                NotifyPayload(
                    channel="email",
                    recipient=user.email,
                    subject=f"Reminder: {todo.title} is due soon",
                    body=(
                        f'Your task "{todo.title}" is due within 24 hours.\n\n'
                        f"Priority: {todo.priority}\n"
                        f"Due Date: {todo.due_date}"
                    ),
                    data={
                        "todo_id": str(todo.id),
                        "type": TODO_DUE_SOON,
                    },
                )
            )

        except Exception as e:
            print(f"Could not queue email reminder: {e}")

    await db.commit()