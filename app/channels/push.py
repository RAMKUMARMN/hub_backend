import logging
import firebase_admin
from firebase_admin import credentials, messaging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (Only once)
try:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK successfully initialized!")
except ValueError:
    pass  # Already initialized
except Exception as e:
    logger.error(f"Failed to load Firebase credentials file: {e}")

async def send_push(
    device_token: str, 
    title: str, 
    body: str, 
    data: Optional[dict[str, Any]] = None
) -> None:
    """Sends a real push notification to a mobile device via FCM."""
    if not device_token:
        logger.warning("Skipping push notification: No device token provided.")
        return

    logger.info(f"Connecting to Firebase to send push to token: {device_token[:10]}...")

    # Build the real FCM payload
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        token=device_token,
    )

    try:
        # Hand it off to Firebase
        response = messaging.send(message)
        logger.info(f"Firebase successfully accepted message! ID: {response}")
    except Exception as e:
        logger.error(f"Firebase Cloud Messaging delivery failed: {e}")
        raise e
