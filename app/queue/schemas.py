from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    """Unified job model tracked across all queues."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType
    queue: str
    attempt: int = 1
    max_attempts: int = 4
    label: str = ""
    payload: dict = {}
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
    payload: dict = {}




