import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class StartSessionRequest(BaseModel):
    type: str = Field("focus", pattern="^(focus|short_break|long_break)$")

class FocusSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    duration_minutes: int | None = None

    class Config:
        from_attributes = True

class ProductivityMetricsResponse(BaseModel):
    total_focus_minutes: int
    total_break_minutes: int
    focus_to_break_ratio: float
    productivity_score: int
