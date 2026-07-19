from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo
from app.models.user_notification import UserNotification
from app.services.email_service import send_email
from app.models.user import User


async def create_due_soon_notifications(db: AsyncSession, manager):
    now = datetime.utcnow()
    soon = now + timedelta(hours=24)

    # STEP 1: Get due todos
    result = await db.execute(
        select(Todo).where(
            Todo.completed == False,
            Todo.due_date <= soon,
            Todo.due_date >= now,
        )
    )

    todos = result.scalars().all()

    for todo in todos:

        # STEP 2: Prevent duplicate notifications
        existing = await db.execute(
            select(UserNotification).where(
                UserNotification.todo_id == todo.id,
                UserNotification.notification_type == "TODO_DUE_SOON",
            )
        )

        if existing.scalar_one_or_none():
            continue  # skip duplicates

        # STEP 3: Create DB notification
        notification = UserNotification(
            user_id=todo.user_id,
            todo_id=todo.id,
            title="Deadline Approaching",
            message=f"Todo '{todo.title}' is due soon!",
            notification_type="TODO_DUE_SOON",
        )

        db.add(notification)

        # STEP 4: WebSocket push
        await manager.send_notification(
            print("SENDING WEBSOCKET NOTIFICATION TO", todo.user_id),
            str(todo.user_id),
            {
                "type": "TODO_DUE_SOON",
                "title": "Deadline Approaching",
                "message": f"Todo '{todo.title}' is due soon!",
                "todo_id": str(todo.id),
            },
        )

        # STEP 5: Email (safe fallback)
        try:
            # IMPORTANT: ensure relationship exists OR fetch user
            user_result = await db.execute(
                select(User).where(User.id == todo.user_id)
            )
            user = user_result.scalar_one_or_none()

            if user:
                await send_email(
                    to_email=user.email,
                    subject="⏰ Todo Deadline Reminder",
                    body=f"Your todo '{todo.title}' is due soon!",
                )

        except Exception as e:
            print("EMAIL FAILED:", e)

    await db.commit()