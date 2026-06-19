import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CreateNoteRequest(BaseModel):
    title: str = Field(..., max_length=500, description="Title of the note")
    content: str | None = Field(None, description="Content of the note")
    tags: list[str] = Field(default_factory=list, description="List of tags associated with the note")
    is_pinned: bool = Field(False, description="Whether the note is pinned")
    is_archived: bool = Field(False, description="Whether the note is archived")


class UpdateNoteRequest(BaseModel):
    title: str | None = Field(None, max_length=500)
    content: str | None = Field(None)
    tags: list[str] | None = Field(None)
    is_pinned: bool | None = Field(None)
    is_archived: bool | None = Field(None)


class ShareNoteRequest(BaseModel):
    email: str = Field(..., description="Email address of the user to share with")


class NoteResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    content: str | None
    tags: list[str]
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
