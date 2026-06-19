import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CreateSubtaskRequest(BaseModel):
    title: str = Field(..., max_length=500, description="Title of the subtask")


class UpdateSubtaskRequest(BaseModel):
    title: str | None = Field(None, max_length=500)
    completed: bool | None = Field(None)


class SubtaskResponse(BaseModel):
    id: uuid.UUID
    todo_id: uuid.UUID
    title: str
    completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}
