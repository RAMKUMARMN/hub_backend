import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CreateFolderRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the document folder")


class FolderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
