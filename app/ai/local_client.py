from __future__ import annotations

import uuid
from typing import AsyncIterator

from app.ai.client import AIClient
from app.ai.services.llm_service import (
    chat_stream as local_chat_stream,
    summarize_text as local_summarize_text,
    get_embedding as local_get_embedding,
    chat_with_tools as local_chat_with_tools,
)
from app.ai.services.vector_service import (
    store_document_vectors as local_store_document_vectors,
    store_image_vectors as local_store_image_vectors,
    search_relevant_chunks as local_search_relevant_chunks,
    delete_document_vectors as local_delete_document_vectors,
)
from app.ai.services.document_service import extract_text as local_extract_text

class LocalAIClient(AIClient):
    """
    Local implementation of AIClient that routes requests directly to
    the backend's local Ollama and Qdrant services.
    """

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
    ) -> AsyncIterator[str]:
        async for token in local_chat_stream(messages, think=think):
            yield token

    async def summarize_text(
        self,
        text: str,
    ) -> str:
        return await local_summarize_text(text)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool = True,
    ) -> dict:
        return await local_chat_with_tools(messages, tools, think=think)

    async def get_embedding(
        self,
        text: str,
    ) -> list[float]:
        return await local_get_embedding(text)

    async def store_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        text: str,
        filename: str = "",
        session_id: uuid.UUID | None = None,
    ) -> int:
        return await local_store_document_vectors(
            user_id=user_id,
            document_id=document_id,
            text=text,
            filename=filename,
            session_id=session_id,
        )

    async def store_image_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        image_metadata: list[dict],
        session_id: uuid.UUID | None = None,
    ) -> int:
        return await local_store_image_vectors(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            image_metadata=image_metadata,
            session_id=session_id,
        )

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
        return await local_search_relevant_chunks(
            user_id=user_id,
            query=query,
            limit=limit,
            retrieval_mode=retrieval_mode,
            use_hyde=use_hyde,
            allowed_document_ids=allowed_document_ids,
            session_id=session_id,
            selected_document_ids=selected_document_ids,
            use_reranker=use_reranker,
            include_meta=include_meta,
        )

    async def delete_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        await local_delete_document_vectors(user_id=user_id, document_id=document_id)

    async def extract_text(
        self,
        file_path: str,
        file_type: str,
    ) -> str:
        return await local_extract_text(file_path=file_path, file_type=file_type)
