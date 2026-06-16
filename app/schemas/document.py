import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID | None = None
    filename: str
    file_type: str
    file_size: int
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}
