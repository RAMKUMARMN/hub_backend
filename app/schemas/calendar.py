import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class CreateCalendarEventRequest(BaseModel):
    title: str = Field(..., max_length=500, description="Title of the event")
    description: str | None = Field(None, description="Description of the event")
    start_time: datetime = Field(..., description="Start time of the event")
    end_time: datetime = Field(..., description="End time of the event")
    is_recurring: bool = Field(False, description="Is it a recurring event")
    recurrence_rule: str | None = Field(None, max_length=255, description="Recurrence description/rule")
    reminder_time: datetime | None = Field(None, description="Time to trigger a reminder notification")
    todo_id: uuid.UUID | None = Field(None, description="Optional associated to-do item ID")

class UpdateCalendarEventRequest(BaseModel):
    title: str | None = Field(None, max_length=500)
    description: str | None = Field(None)
    start_time: datetime | None = Field(None)
    end_time: datetime | None = Field(None)
    is_recurring: bool | None = Field(None)
    recurrence_rule: str | None = Field(None, max_length=255)
    reminder_time: datetime | None = Field(None)
    todo_id: uuid.UUID | None = Field(None)

class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    is_recurring: bool
    recurrence_rule: str | None = None
    reminder_time: datetime | None = None
    todo_id: uuid.UUID | None = None

    class Config:
        from_attributes = True
