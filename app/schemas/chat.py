import uuid
from datetime import datetime



from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"

class UpdateSessionRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str
    use_rag: bool = False


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
