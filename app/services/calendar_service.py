import uuid
import logging
import httpx
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.calendar import CalendarEvent
from app.models.todo import Todo
from app.schemas.calendar import CreateCalendarEventRequest, UpdateCalendarEventRequest
from app.models.user import User
from app.queue.producer import publish_notification_to_queue

logger = logging.getLogger(__name__)

def get_google_event_id(description: str | None) -> str | None:
    if not description:
        return None
    marker = "[Google Event ID: "
    if marker in description:
        parts = description.split(marker)
        if len(parts) > 1:
            return parts[1].split("]")[0].strip()
    return None

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self, 
        user_id: uuid.UUID, 
        body: CreateCalendarEventRequest, 
        google_token: str | None = None
    ) -> CalendarEvent:
        if body.todo_id:
            todo_exists = await self.db.execute(
                select(Todo).where(Todo.id == body.todo_id, Todo.user_id == user_id)
            )
            if not todo_exists.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Associated todo item not found or not owned by user"
                )

        desc_to_save = body.description or ""
        google_event_id = None
        
        if google_token:
            try:
                async with httpx.AsyncClient() as client:
                    google_payload = {
                        "summary": body.title,
                        "description": body.description,
                        "start": {
                            "dateTime": body.start_time.isoformat()
                        },
                        "end": {
                            "dateTime": body.end_time.isoformat()
                        }
                    }
                    headers = {"Authorization": f"Bearer {google_token}"}
                    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
                    resp = await client.post(url, headers=headers, json=google_payload, timeout=10)
                    if resp.status_code in (200, 201):
                        google_event_id = resp.json().get("id")
                        if google_event_id:
                            if desc_to_save:
                                desc_to_save += f"\n\n[Google Event ID: {google_event_id}]"
                            else:
                                desc_to_save = f"[Google Event ID: {google_event_id}]"
                    else:
                        logger.error("Google Calendar API returned error status %s: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("Failed to push created event to Google Calendar: %s", e)

        event = CalendarEvent(
            user_id=user_id,
            title=body.title,
            description=desc_to_save,
            start_time=body.start_time,
            end_time=body.end_time,
            is_recurring=body.is_recurring,
            recurrence_rule=body.recurrence_rule,
            reminder_time=body.reminder_time,
            todo_id=body.todo_id
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        if event.reminder_time:
            try:
                user_res = await self.db.execute(select(User).where(User.id == user_id))
                user = user_res.scalar_one_or_none()
                if user and user.email:
                    await publish_notification_to_queue(
                        channel="email",
                        recipient=user.email,
                        subject=f"Event Reminder: {event.title}",
                        body=f"This is a reminder for your event: {event.title}. Scheduled to start at: {event.start_time.isoformat()}.",
                        html_body=f"<p>This is a reminder for your event: <strong>{event.title}</strong>.<br>Scheduled to start at: {event.start_time.isoformat()}.</p>",
                        message_type="calendar_reminder",
                        priority="medium",
                    )
            except Exception:
                pass

        return event

    async def get_event(self, event_id: uuid.UUID, user_id: uuid.UUID) -> CalendarEvent:
        result = await self.db.execute(
            select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        return event

    async def list_events(self, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None) -> list[CalendarEvent]:
        query = select(CalendarEvent).where(CalendarEvent.user_id == user_id).order_by(CalendarEvent.start_time.asc())
        if start:
            query = query.where(CalendarEvent.start_time >= start)
        if end:
            query = query.where(CalendarEvent.end_time <= end)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_event(
        self, 
        event_id: uuid.UUID, 
        user_id: uuid.UUID, 
        body: UpdateCalendarEventRequest, 
        google_token: str | None = None
    ) -> CalendarEvent:
        event = await self.get_event(event_id, user_id)

        if body.todo_id is not None:
            if body.todo_id:
                todo_exists = await self.db.execute(
                    select(Todo).where(Todo.id == body.todo_id, Todo.user_id == user_id)
                )
                if not todo_exists.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Associated todo item not found or not owned by user"
                    )
                event.todo_id = body.todo_id
            else:
                event.todo_id = None

        new_title = body.title if body.title is not None else event.title
        new_desc = body.description if body.description is not None else (event.description or "")
        new_start = body.start_time if body.start_time is not None else event.start_time
        new_end = body.end_time if body.end_time is not None else event.end_time

        google_event_id = get_google_event_id(event.description)

        if google_token and google_event_id:
            try:
                # Strip Google ID marker from description when pushing update to Google
                clean_desc = new_desc
                marker = "[Google Event ID: "
                if marker in clean_desc:
                    clean_desc = clean_desc.split(marker)[0].strip()

                async with httpx.AsyncClient() as client:
                    google_payload = {
                        "summary": new_title,
                        "description": clean_desc,
                        "start": {
                            "dateTime": new_start.isoformat()
                        },
                        "end": {
                            "dateTime": new_end.isoformat()
                        }
                    }
                    headers = {"Authorization": f"Bearer {google_token}"}
                    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
                    resp = await client.put(url, headers=headers, json=google_payload, timeout=10)
                    if resp.status_code not in (200, 201):
                        logger.error("Failed to update Google event. Status %s: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("Failed to update event on Google Calendar: %s", e)

        if body.title is not None:
            event.title = body.title
        if body.description is not None:
            if google_event_id and f"[Google Event ID: {google_event_id}]" not in body.description:
                event.description = body.description + f"\n\n[Google Event ID: {google_event_id}]"
            else:
                event.description = body.description
        elif google_event_id and event.description and f"[Google Event ID: {google_event_id}]" not in event.description:
            # Re-append if it was somehow lost
            event.description += f"\n\n[Google Event ID: {google_event_id}]"
            
        if body.start_time is not None:
            event.start_time = body.start_time
        if body.end_time is not None:
            event.end_time = body.end_time
        if body.is_recurring is not None:
            event.is_recurring = body.is_recurring
        if body.recurrence_rule is not None:
            event.recurrence_rule = body.recurrence_rule
        
        old_reminder = event.reminder_time
        if body.reminder_time is not None:
            event.reminder_time = body.reminder_time
            if event.reminder_time and event.reminder_time != old_reminder:
                try:
                    user_res = await self.db.execute(select(User).where(User.id == user_id))
                    user = user_res.scalar_one_or_none()
                    if user and user.email:
                        await publish_notification_to_queue(
                            channel="email",
                            recipient=user.email,
                            subject=f"Event Reminder: {event.title}",
                            body=f"This is a reminder for your event: {event.title}. Scheduled to start at: {event.start_time.isoformat()}.",
                            html_body=f"<p>This is a reminder for your event: <strong>{event.title}</strong>.<br>Scheduled to start at: {event.start_time.isoformat()}.</p>",
                            message_type="calendar_reminder",
                            priority="medium",
                        )
                except Exception:
                    pass

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete_event(self, event_id: uuid.UUID, user_id: uuid.UUID, google_token: str | None = None) -> None:
        event = await self.get_event(event_id, user_id)
        
        google_event_id = get_google_event_id(event.description)
        if google_token and google_event_id:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {google_token}"}
                    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
                    resp = await client.delete(url, headers=headers, timeout=10)
                    if resp.status_code not in (200, 204):
                        logger.error("Failed to delete Google event. Status %s: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("Failed to delete event from Google Calendar: %s", e)

        await self.db.delete(event)
        await self.db.commit()
