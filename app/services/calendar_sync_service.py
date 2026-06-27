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

    async def sync_with_google(self, user_id: uuid.UUID, google_token: str) -> dict:
        """
        Synchronize with Google Calendar using the provided Google access token.
        - Fetches primary calendar events from the last 30 days to 30 days in the future.
        - Checks for duplicates in the local database.
        - Imports new events and saves them with a special sync marker.
        - Removes local events that have the sync marker but are no longer in Google Calendar.
        - Updates the sync status in Redis.
        """
        import httpx
        redis_key = f"calendar:last_sync:{user_id}"
        sync_marker = "[Synced from Google Calendar]"
        
        # Get all local events for this user
        result = await self.db.execute(
            select(CalendarEvent).where(CalendarEvent.user_id == user_id)
        )
        local_events = result.scalars().all()
        logger.info(f"Syncing Google Calendar: found {len(local_events)} local events to export.")

        # Fetch events from Google Calendar API using the token
        headers = {"Authorization": f"Bearer {google_token}"}
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        
        time_min = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        params = {
            "timeMin": time_min,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        
        imported_count = 0
        deleted_count = 0
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 401:
                    logger.error("Google OAuth token expired or invalid.")
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Google OAuth token expired or invalid. Please sign in again."
                    )
                elif response.status_code != 200:
                    logger.error(f"Google Calendar API failed with status {response.statusCode if hasattr(response, 'statusCode') else response.status_code}: {response.text}")
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail=f"Failed to fetch Google Calendar events: {response.text}")
                
                events_data = response.json().get("items", [])
                
                # Keep track of active Google event keys
                google_event_keys = set()
                
                for item in events_data:
                    title = item.get("summary", "No Title")
                    description = item.get("description", "")
                    
                    start_data = item.get("start", {})
                    end_data = item.get("end", {})
                    
                    start_str = start_data.get("dateTime") or start_data.get("date")
                    end_str = end_data.get("dateTime") or end_data.get("date")
                    
                    if not start_str:
                        continue
                    
                    # Parse start and end times
                    if "T" not in start_str:
                        # All-day event
                        start_time = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
                    else:
                        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        
                    if not end_str:
                        end_time = start_time + timedelta(hours=1)
                    elif "T" not in end_str:
                        # All-day event
                        end_time = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
                    else:
                        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

                    # Add to active google keys (normalized to UTC)
                    google_event_keys.add((title, start_time.astimezone(timezone.utc)))

                    # Recurrence mapping
                    recurrence = item.get("recurrence", [])
                    is_recurring = len(recurrence) > 0
                    recurrence_rule = recurrence[0] if is_recurring else None

                    # Check if event already exists in database
                    exists_result = await self.db.execute(
                        select(CalendarEvent).where(
                            CalendarEvent.user_id == user_id,
                            CalendarEvent.title == title,
                            CalendarEvent.start_time == start_time
                        )
                    )
                    existing_event = exists_result.scalar_one_or_none()
                    
                    if not existing_event:
                        # Add sync marker to description
                        desc_with_marker = (description or "")
                        if sync_marker not in desc_with_marker:
                            desc_with_marker += f"\n\n{sync_marker}"
                            
                        new_event = CalendarEvent(
                            user_id=user_id,
                            title=title,
                            description=desc_with_marker,
                            start_time=start_time,
                            end_time=end_time,
                            is_recurring=is_recurring,
                            recurrence_rule=recurrence_rule
                        )
                        self.db.add(new_event)
                        imported_count += 1

                # Clean up local events that have the marker but are no longer in Google Calendar
                local_google_result = await self.db.execute(
                    select(CalendarEvent).where(
                        CalendarEvent.user_id == user_id,
                        CalendarEvent.description.like(f"%{sync_marker}%")
                    )
                )
                local_google_events = local_google_result.scalars().all()
                
                for local_ev in local_google_events:
                    local_key = (local_ev.title, local_ev.start_time.astimezone(timezone.utc))
                    if local_key not in google_event_keys:
                        await self.db.delete(local_ev)
                        deleted_count += 1
                        
                if imported_count > 0 or deleted_count > 0:
                    await self.db.commit()
                    if imported_count > 0:
                        logger.info(f"Imported {imported_count} new events from Google Calendar.")
                    if deleted_count > 0:
                        logger.info(f"Deleted {deleted_count} stale events that were removed from Google Calendar.")
                    
        except Exception as e:
            if isinstance(e, Exception) and "HTTPException" in str(type(e)):
                raise e
            logger.error(f"Error during Google Calendar sync: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Google Calendar sync failed: {str(e)}")

        # Update last sync timestamp in Redis
        now_str = datetime.now(timezone.utc).isoformat()
        await redis_client.set(redis_key, now_str)

        return {
            "status": "success",
            "message": "Google Calendar sync completed successfully.",
            "last_sync": now_str,
            "exported_count": len(local_events),
            "imported_count": imported_count,
            "deleted_count": deleted_count
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
