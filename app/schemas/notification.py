import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationJobResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    payload: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }