import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str
    use_rag: bool = False
    use_hyde: bool = False
    web_search: bool = False
    thinking_mode: bool = True
    retrieval_mode: Literal["semantic", "keyword", "hybrid"] = "semantic"
    rag_chunk_limit: int = Field(default=4, ge=4, le=64)
    document_ids: list[uuid.UUID] | None = None
    use_reranker: bool = False

    """
    Optional list of specific document IDs to restrict RAG search to.
    Only documents that are global (no session) or belong to the current session
    are permitted — documents from other sessions are silently excluded.
    If None (default), all allowed documents for the session are searched.
    """


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    thinking: str | None = None
    sources: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
