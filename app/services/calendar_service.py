import uuid
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.calendar import CalendarEvent
from app.models.todo import Todo
from app.schemas.calendar import CreateCalendarEventRequest, UpdateCalendarEventRequest
from app.queue.producer import publish_calendar_notification

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, user_id: uuid.UUID, body: CreateCalendarEventRequest) -> CalendarEvent:
        if body.todo_id:
            todo_exists = await self.db.execute(
                select(Todo).where(Todo.id == body.todo_id, Todo.user_id == user_id)
            )
            if not todo_exists.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Associated todo item not found or not owned by user"
                )

        event = CalendarEvent(
            user_id=user_id,
            title=body.title,
            description=body.description,
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
                await publish_calendar_notification({
                    "user_id": str(user_id),
                    "event_id": str(event.id),
                    "title": event.title,
                    "reminder_time": event.reminder_time.isoformat()
                })
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

    async def update_event(self, event_id: uuid.UUID, user_id: uuid.UUID, body: UpdateCalendarEventRequest) -> CalendarEvent:
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

        if body.title is not None:
            event.title = body.title
        if body.description is not None:
            event.description = body.description
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
                    await publish_calendar_notification({
                        "user_id": str(user_id),
                        "event_id": str(event.id),
                        "title": event.title,
                        "reminder_time": event.reminder_time.isoformat()
                    })
                except Exception:
                    pass

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete_event(self, event_id: uuid.UUID, user_id: uuid.UUID) -> None:
        event = await self.get_event(event_id, user_id)
        await self.db.delete(event)
        await self.db.commit()
