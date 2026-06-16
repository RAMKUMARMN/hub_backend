import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateNotificationJobRequest(BaseModel):
    channel: str       # 'email' | 'sms' | 'push' | 'whatsapp'
    total: int


class NotificationJobResponse(BaseModel):
    id: uuid.UUID
    channel: str
    total: int
    sent: int
    failed: int
    retrying: int
    completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}