from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==========================================================
# Generic Job Queue
# ==========================================================

class JobType(str, Enum):
    FILE_UPLOAD = "file_upload"
    RAG_BULK_INGEST = "rag_bulk_ingest"
    BULK_EMAIL = "bulk_email"
    BULK_SMS = "bulk_sms"
    ANALYTICS = "analytics"
    AI_ORCHESTRATION = "ai_orchestration"
    EMBEDDING_PROCESSING = "embedding_processing"
    MEMORY_PROCESSING = "memory_processing"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    RETRYING = "retrying"
    DLQ = "dlq"


class Job(BaseModel):
    """
    Generic RabbitMQ Job.
    """

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    job_type: JobType

    queue: str

    attempt: int = 1

    max_attempts: int = 4

    label: str = ""

    payload: dict = Field(default_factory=dict)

    status: JobStatus = JobStatus.QUEUED

    progress: int = 0

    message: str = ""

    total: int = 0

    done_count: int = 0

    created_at: str = Field(default_factory=_now)

    updated_at: str = Field(default_factory=_now)


class SubmitJobRequest(BaseModel):
    job_type: JobType

    label: str = ""

    payload: dict = Field(default_factory=dict)


# ==========================================================
# Notification Queue Payload
# ==========================================================

NotificationChannel = Literal[
    "email",
    "sms",
    "push",
    "whatsapp",
]


class NotifyPayload(BaseModel):
    """
    Payload consumed by the Notification Service.
    """

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    channel: NotificationChannel

    recipient: str

    body: str

    subject: str | None = None

    title: str | None = None

    html_body: str | None = None

    data: dict = Field(default_factory=dict)

    attempt: int = 1

    max_attempts: int = 4