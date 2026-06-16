"""
Vector service — Qdrant storage + Ollama nomic-embed-text embeddings.

Responsibilities:
  - Initialize Qdrant collection (768-dim, cosine) and full-text payload index on startup.
  - Generate embeddings via local Ollama nomic-embed-text model.
  - Paragraph-aware text chunking (splits on blank lines, overlapping context window).
  - Multi-tenant vector upsert: each point carries user_id in payload for isolation.
  - Semantic similarity search filtered strictly by user_id.
  - Full clean-up when a document is deleted.
"""
from __future__ import annotations

import uuid
import logging

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    MatchAny,
    PointStruct,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level async client — shared across all requests.
qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------

async def init_qdrant_collection() -> None:
    """
    Called once during application startup (from main.py lifespan).

    - Creates the Qdrant collection if it does not already exist.
    - Adds a multilingual full-text payload index on the 'text' field so that
      exact keyword queries (course codes, function names, etc.) work alongside
      vector cosine search.
    """
    try:
        exists = await qdrant_client.collection_exists(
            collection_name=settings.qdrant_collection
        )
        if not exists:
            await qdrant_client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=768,           # nomic-embed-text output dimension
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Qdrant collection '%s' created.", settings.qdrant_collection)

            # Add keyword payload index for hybrid search (vector + full-text).
            await qdrant_client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="text",
                field_schema=TextIndexParams(
                    type="text",
                    tokenizer=TokenizerType.MULTILINGUAL,
                    lowercase=True,
                ),
            )
            logger.info("Full-text payload index created on 'text' field.")
        else:
            logger.info("Qdrant collection '%s' already exists.", settings.qdrant_collection)
    except Exception as exc:
        logger.warning(
            "Failed to initialise Qdrant collection (is Qdrant running?): %s. "
            "Vector search and document processing features will be unavailable.",
            exc,
            exc_info=settings.debug
        )


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

async def get_ollama_embedding(text: str) -> list[float]:
    """
    Generate a 768-dimensional text embedding using Ollama's nomic-embed-text model.

    Calls the local Ollama REST API:
      POST /api/embeddings  { "model": "nomic-embed-text", "prompt": "<text>" }

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={
                "model": settings.ollama_embed_model,
                "prompt": text,
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Paragraph-aware text chunker.

    Splits the document on blank-line paragraph boundaries first so that
    headings, code blocks, and lists are never cut in half.  Whenever the
    accumulated paragraph group exceeds chunk_size characters it is flushed
    as a chunk and the last `overlap` characters are carried forward so that
    consecutive chunks share context.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Carry the tail of the previous chunk forward for context overlap.
            current_chunk = current_chunk[-overlap:] if len(current_chunk) > overlap else ""

        current_chunk += ("\n\n" + para if current_chunk else para)

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

async def store_document_vectors(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    text: str,
    filename: str = "",
    session_id: uuid.UUID | None = None,
) -> int:
    """
    Chunk, embed, and upsert a document into Qdrant.

    Each Qdrant point carries the following payload for filtering and citation:
      user_id      — for multi-tenant isolation in every search query
      document_id  — to allow targeted deletion
      session_id   — to track the scope of local/session documents
      filename     — displayed in source citation cards on the frontend
      text         — the raw chunk text returned during retrieval
      chunk_index  — preserves ordering for potential re-assembly

    Returns the number of chunks stored.
    """
    chunks = chunk_text(text)
    if not chunks:
        logger.warning("Document %s produced no text chunks.", document_id)
        return 0

    points: list[PointStruct] = []
    for idx, chunk in enumerate(chunks):
        embedding = await get_ollama_embedding(chunk)
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    "session_id": str(session_id) if session_id else None,
                    "filename": filename,
                    "text": chunk,
                    "chunk_index": idx,
                },
            )
        )

    await qdrant_client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
    )
    logger.info(
        "Stored %d chunks for document %s (user %s).", len(points), document_id, user_id
    )
    return len(points)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

async def search_relevant_chunks(
    user_id: uuid.UUID,
    query: str,
    limit: int = 4,
    allowed_document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """
    Retrieve the top-`limit` document chunks most semantically similar to `query`.

    The Qdrant filter restricts results exclusively to vectors that belong to
    the authenticated user — guaranteeing complete multi-tenant data isolation.

    If allowed_document_ids is provided, restricts search exclusively to those documents.

    Returns a list of dicts:
      { "text": str, "filename": str, "document_id": str }
    These are forwarded directly to the SSE stream as a 'sources' event so the
    frontend can render clickable citation badges.
    """
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    query_vector = await get_ollama_embedding(query)

    must_conditions = [
        FieldCondition(
            key="user_id",
            match=MatchValue(value=str(user_id)),
        )
    ]

    if allowed_document_ids is not None:
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchAny(any=[str(doc_id) for doc_id in allowed_document_ids]),
            )
        )

    results = await qdrant_client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=limit,
    )

    return [
        {
            "text": hit.payload.get("text", ""),
            "filename": hit.payload.get("filename", "Unknown"),
            "document_id": hit.payload.get("document_id", ""),
        }
        for hit in results.points
    ]


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

async def delete_document_vectors(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """
    Remove all Qdrant vectors for a given document belonging to a specific user.

    Uses a compound filter (user_id AND document_id) so that a user can never
    accidentally delete vectors owned by someone else.
    """
    await qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=str(user_id)),
                ),
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=str(document_id)),
                ),
            ]
        ),
    )
    logger.info(
        "Deleted Qdrant vectors for document %s (user %s).", document_id, user_id
    )
