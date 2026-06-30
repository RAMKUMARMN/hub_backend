from __future__ import annotations

import uuid
from typing import Protocol, AsyncIterator
from app.config import settings

class AIClient(Protocol):
    """
    Contract for all AI operations required by the CixioHub backend.
    Enables swapping local service execution (Ollama/Qdrant) with remote microservice API proxy.
    """

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from LLM."""
        ...

    async def summarize_text(
        self,
        text: str,
    ) -> str:
        """Summarize conversational history/text using LLM."""
        ...

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool = True,
    ) -> dict:
        """One-shot chat completion with support for tool/function calling."""
        ...

    async def get_embedding(
        self,
        text: str,
    ) -> list[float]:
        """Generate a text embedding vector."""
        ...

    async def store_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        text: str,
        filename: str = "",
        session_id: uuid.UUID | None = None,
    ) -> int:
        """Chunk, embed, and upload document vectors to storage."""
        ...

    async def store_image_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        image_metadata: list[dict],
        session_id: uuid.UUID | None = None,
    ) -> int:
        """Process, describe, embed, and store image vectors for a document."""
        ...

    async def search_relevant_chunks(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 4,
        retrieval_mode: str = "semantic",
        use_hyde: bool = False,
        allowed_document_ids: list[uuid.UUID] | None = None,
        session_id: uuid.UUID | None = None,
        selected_document_ids: list[uuid.UUID] | None = None,
        use_reranker: bool = False,
        include_meta: bool = False,
    ) -> list[dict]:
        """Search relevant document chunks by query similarity."""
        ...

    async def delete_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        """Delete vector storage points for a document."""
        ...

    async def extract_text(
        self,
        file_path: str,
        file_type: str,
    ) -> str:
        """Extract text from a file (e.g. PDF/DOCX/OCR)."""
        ...


_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """
    Dependency helper to retrieve the correct configured AIClient instance.
    """
    global _client
    if _client is None:
        if settings.use_remote_ai:
            from app.ai.remote_client import RemoteAIClient
            _client = RemoteAIClient()
        else:
            from app.ai.local_client import LocalAIClient
            _client = LocalAIClient()
    return _client
