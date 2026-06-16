"""
RAG service — thin wrappers delegating to vector_service.

Previously, these functions proxied requests to an external AI microservice.
They now delegate directly to the local Qdrant + Ollama pipeline implemented
in vector_service.py.

Kept for backwards compatibility with any code that still imports from here.
"""
from __future__ import annotations

import uuid

from app.services.vector_service import (
    delete_document_vectors,
    search_relevant_chunks,
    store_document_vectors,
)


async def ingest_document(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    text: str,
    filename: str = "",
    session_id: uuid.UUID | None = None,
) -> int:
    """
    Chunk, embed via nomic-embed-text, and store in Qdrant.
    Returns the number of chunks stored.
    """
    return await store_document_vectors(
        user_id=user_id,
        document_id=document_id,
        text=text,
        filename=filename,
        session_id=session_id,
    )


async def retrieve_chunks(
    user_id: uuid.UUID,
    query: str,
    n_results: int = 4,
) -> list[str]:
    """
    Retrieve the top-n_results document text chunks relevant to `query`.
    Filtered to the authenticated user's documents only.
    Returns a list of plain text strings.
    """
    results = await search_relevant_chunks(
        user_id=user_id,
        query=query,
        limit=n_results,
    )
    return [item["text"] for item in results]


async def delete_document_chunks(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """Remove all Qdrant vectors for a given document belonging to the user."""
    await delete_document_vectors(user_id=user_id, document_id=document_id)
