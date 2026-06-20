from app.models.notification import Notification


def update_status(
    db,
    notification_id,
    status
):

    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if notification:

        notification.status = status

        db.commit()


def increment_attempt(
    db,
    notification_id
):

    notification = db.query(
        Notification
    ).filter(
        Notification.id == notification_id
    ).first()

    if notification:

        notification.attempts += 1

        db.commit()