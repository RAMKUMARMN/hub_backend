"""Minimal NotifyPayload schema used by worker stub/testing."""
from typing import Any, Dict, Optional

from pydantic import BaseModel


class NotifyPayload(BaseModel):
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    title: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None
    attempt: int = 1
    max_attempts: int = 4
