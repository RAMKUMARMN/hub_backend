from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_notification import UserNotification


async def create_notification(
    db: AsyncSession,
    user_id,
    title: str,
    message: str,
    notification_type: str,
):
    notification = UserNotification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
    )

    db.add(notification)
    return notification