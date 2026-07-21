"""
RAG service — proxies ingest / retrieve / delete requests to the AI service.

The AI service (cixio-hub/ai, port 8003) handles:
  - Text chunking (~500 tokens, 50 overlap)
  - Embedding via Ollama nomic-embed-text
  - ChromaDB storage (per-user collections)
  - Cosine similarity retrieval

Students (AI/LLM role): implement the RAG pipeline in cixio-hub/ai.
Students (Backend role): this file is already wired.
"""

from __future__ import annotations

import uuid

import httpx

from app.config import settings


async def ingest_document(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    text: str,
    filename: str = "",
) -> int:
    """
    Send extracted text to the AI service for chunking, embedding, and storage.
    Returns the number of chunks stored.
    """
    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=120
    ) as client:
        response = await client.post(
            "/api/v1/rag/ingest",
            json={
                "user_id": str(user_id),
                "document_id": str(document_id),
                "text": text,
                "filename": filename,
            },
        )
        response.raise_for_status()
        return response.json()["chunks_stored"]


async def retrieve_chunks(
    user_id: uuid.UUID,
    query: str,
    n_results: int = 5,
) -> list[str]:
    """
    Ask the AI service for top-k chunks most relevant to the query.
    Returns a list of chunk text strings.
    """
    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=30
    ) as client:
        response = await client.post(
            "/api/v1/rag/retrieve",
            json={
                "user_id": str(user_id),
                "query": query,
                "top_k": n_results,
            },
        )
        response.raise_for_status()
        return response.json()["chunks"]


async def delete_document_chunks(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """Remove all ChromaDB chunks for a document via the AI service."""
    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=30
    ) as client:
        response = await client.delete(
            f"/api/v1/rag/documents/{document_id}",
            params={"user_id": str(user_id)},
        )
        response.raise_for_status()
