from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.email_service import send_email
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_notification import UserNotification
from app.services.todo_reminder_service import create_due_soon_notifications
from app.websocket_manager import manager

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotification)
        .where(UserNotification.user_id == current_user.id)
        .order_by(UserNotification.created_at.desc())
    )

    return result.scalars().all()


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == current_user.id,
        )
    )

    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    notification.is_read = True

    await db.commit()

    return {
        "message": "Notification marked as read"
    }


@router.get("/unread-count")
async def unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count())
        .select_from(UserNotification)
        .where(
            UserNotification.user_id == current_user.id,
            UserNotification.is_read == False,
        )
    )

    count = result.scalar()

    return {
        "count": count
    }


@router.post("/run-reminders")
async def run_reminders(
    db: AsyncSession = Depends(get_db),
):
    await create_due_soon_notifications(db,manager)

    return {
        "message": "Reminder job executed"
    }


@router.post("/test-push")
async def test_push_notification(
    current_user: User = Depends(get_current_user),
):
    payload = {
        "type": "TEST_NOTIFICATION",
        "title": "WebSocket Test",
        "message": "Real-time notification working successfully!"
    }

    await manager.send_notification(
        str(current_user.id),
        payload,
    )

    return {
        "message": "Notification pushed successfully"
    }

@router.post("/test-email")
async def test_email():
    await send_email(
        to_email="vedhak09@gmail.com",
        subject="CixioHub Test Email",
        body="Email notifications are working successfully."
    )

    return {
        "message": "Email sent successfully"
    }