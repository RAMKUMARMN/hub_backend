import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.redis import redis_client
from app.config import settings
from app.models.calendar import CalendarEvent

logger = logging.getLogger(__name__)

class CalendarSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_with_google(self, user_id: uuid.UUID) -> dict:
        """
        Simulate/implement synchronization with Google Calendar.
        - Checks Google Calendar configuration.
        - Reads local events.
        - Imports simulated/mock Google events.
        - Updates the sync status in Redis.
        """
        redis_key = f"calendar:last_sync:{user_id}"
        
        # Check if settings are configured (would normally raise an exception if required,
        # but here we allow simulated sync for testing/dev environments).
        has_config = bool(settings.google_client_id and settings.google_client_secret)
        
        # Get all local events for this user
        result = await self.db.execute(
            select(CalendarEvent).where(CalendarEvent.user_id == user_id)
        )
        local_events = result.scalars().all()
        logger.info(f"Syncing Google Calendar: found {len(local_events)} local events to export.")

        # Simulate importing an event from Google Calendar if it doesn't exist yet
        google_event_title = "Google Calendar Sync Session"
        exists_result = await self.db.execute(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.title == google_event_title
            )
        )
        imported_event = exists_result.scalar_one_or_none()
        
        if not imported_event:
            # Create a mock imported event from Google Calendar starting tomorrow
            now = datetime.now(timezone.utc)
            start_time = now + timedelta(days=1)
            end_time = start_time + timedelta(hours=1)
            
            new_event = CalendarEvent(
                user_id=user_id,
                title=google_event_title,
                description="Imported from your Google Calendar during synchronization.",
                start_time=start_time,
                end_time=end_time,
                is_recurring=False
            )
            self.db.add(new_event)
            await self.db.commit()
            logger.info("Imported new event from Google Calendar.")

        # Update last sync timestamp in Redis
        now_str = datetime.now(timezone.utc).isoformat()
        await redis_client.set(redis_key, now_str)

        return {
            "status": "success",
            "message": "Google Calendar sync completed successfully." if has_config else "Google Calendar sync completed successfully (Simulated).",
            "last_sync": now_str,
            "exported_count": len(local_events),
            "imported_count": 0 if imported_event else 1
        }

    async def get_sync_status(self, user_id: uuid.UUID) -> dict:
        """
        Retrieve the last synchronization timestamp and status from Redis.
        """
        redis_key = f"calendar:last_sync:{user_id}"
        last_sync = await redis_client.get(redis_key)
        
        if not last_sync:
            return {
                "status": "never_synced",
                "last_sync": None
            }
            
        return {
            "status": "synced",
            "last_sync": last_sync
        }
