from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


TodoPriority = Literal["low", "medium", "high"]


class CreateTodoRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    due_date: datetime | None = None
    priority: TodoPriority = "medium"
    reminder_at: datetime | None = None


class UpdateTodoRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    due_date: datetime | None = None
    priority: TodoPriority | None = None
    reminder_at: datetime | None = None


class CompleteToggleRequest(BaseModel):
    completed: bool


class TodoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    description: str | None
    completed: bool
    due_date: datetime | None
    priority: TodoPriority
    reminder_at: datetime | None
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime