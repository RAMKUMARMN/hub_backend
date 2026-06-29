import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User
from app.schemas.calendar import CreateCalendarEventRequest, UpdateCalendarEventRequest, CalendarEventResponse
from app.services.calendar_service import CalendarService
from app.services.dashboard_service import invalidate_dashboard_cache

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: CreateCalendarEventRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    event = await CalendarService(db).create_event(current_user.id, body)

    await invalidate_dashboard_cache(current_user.id)

    return event

@router.get("/events", response_model=list[CalendarEventResponse])
async def list_events(
    start: datetime | None = Query(None, description="Start date/time to filter events"),
    end: datetime | None = Query(None, description="End date/time to filter events"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await CalendarService(db).list_events(current_user.id, start, end)

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await CalendarService(db).get_event(event_id, current_user.id)

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: UpdateCalendarEventRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    event = await CalendarService(db).update_event(
        event_id,
        current_user.id,
        body
    )

    await invalidate_dashboard_cache(current_user.id)

    return event

@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await CalendarService(db).delete_event(
        event_id,
        current_user.id
    )

    await invalidate_dashboard_cache(current_user.id)


# Sync endpoints
from app.services.calendar_sync_service import CalendarSyncService


@router.post("/sync/google")
async def sync_google_calendar(
    google_token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await CalendarSyncService(db).sync_with_google(current_user.id, google_token)


@router.get("/sync/status")
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await CalendarSyncService(db).get_sync_status(current_user.id)