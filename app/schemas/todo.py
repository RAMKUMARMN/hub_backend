import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.schemas.subtask import SubtaskResponse


class CreateTodoRequest(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    reminder_time: datetime | None = None


class UpdateTodoRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    priority: Literal["low", "medium", "high"] | None = None
    reminder_time: datetime | None = None


class CompleteToggleRequest(BaseModel):
    completed: bool


class TodoResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    completed: bool
    due_date: datetime | None
    priority: Literal["low", "medium", "high"]
    reminder_time: datetime | None
    subtasks: list[SubtaskResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

