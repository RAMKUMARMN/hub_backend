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
import re

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
    PayloadSchemaType,
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

            # Create payload indexes on user_id and session_id for multi-tenant isolation.
            await qdrant_client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="user_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            await qdrant_client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="session_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.info("Payload indexes created on 'user_id' and 'session_id' fields.")
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

async def get_ollama_embedding(text: str, prefix_type: str | None = None) -> list[float]:
    """
    Generate a 768-dimensional text embedding using Ollama's nomic-embed-text model.

    Calls the local Ollama REST API:
      POST /api/embeddings  { "model": "nomic-embed-text", "prompt": "<text>" }

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    prefix = ""
    if prefix_type == "query":
        prefix = "search_query: "
    elif prefix_type == "document":
        prefix = "search_document: "

    formatted_text = prefix + text

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={
                "model": settings.ollama_embed_model,
                "prompt": formatted_text,
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def get_clean_overlap(chunk: str, overlap: int) -> str:
    if not chunk or overlap <= 0:
        return ""
    raw = chunk[-overlap:] if len(chunk) > overlap else chunk
    if len(chunk) > overlap:
        char_before = chunk[-overlap - 1]
        if char_before not in (" ", "\n") and raw[0] not in (" ", "\n"):
            idx = -1
            first_space = raw.find(" ")
            first_newline = raw.find("\n")
            if first_space != -1 and first_newline != -1:
                idx = min(first_space, first_newline)
            elif first_space != -1:
                idx = first_space
            elif first_newline != -1:
                idx = first_newline
            
            if idx != -1:
                raw = raw[idx + 1:]
            else:
                raw = ""
    return raw

def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Paragraph-aware text chunker.

    Splits the document on blank-line paragraph boundaries first so that
    headings, code blocks, and lists are never cut in half. If an individual
    paragraph exceeds chunk_size, it is recursively split into sentences to
    prevent oversized chunks.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph is larger than chunk_size, recursively split it
        if len(para) > chunk_size:
            # Flush the current chunk first if it exists
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = get_clean_overlap(current_chunk, overlap)

            # Split the long paragraph into sentences (preserving punctuation)
            sentences = re.split(r"(?<=[.!?])\s+", para)
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # If a single sentence is larger than chunk_size, split by words
                if len(sentence) > chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""
                    
                    words = sentence.split(" ")
                    for word in words:
                        if not word:
                            continue
                        if len(current_chunk) + len(word) + 1 > chunk_size and current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = get_clean_overlap(current_chunk, overlap)
                        current_chunk += (" " + word if current_chunk else word)
                else:
                    if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = get_clean_overlap(current_chunk, overlap)
                    current_chunk += (" " + sentence if current_chunk else sentence)
        else:
            if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = get_clean_overlap(current_chunk, overlap)
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
        embedding = await get_ollama_embedding(chunk, prefix_type="document")
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
    session_id: uuid.UUID | None = None,
    selected_document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """
    Retrieve the top-`limit` document chunks most semantically similar to `query`.

    The Qdrant filter restricts results exclusively to vectors that belong to
    the authenticated user — guaranteeing complete multi-tenant data isolation.

    If allowed_document_ids is provided, restricts search exclusively to those documents.

    If session_id is provided, candidates are retrieved and prioritized by adding a
    similarity score boost to those documents belonging to the current session.

    Returns a list of dicts:
      { "text": str, "filename": str, "document_id": str }
    These are forwarded directly to the SSE stream as a 'sources' event so the
    frontend can render clickable citation badges.
    """
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    query_vector = await get_ollama_embedding(query, prefix_type="query")

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

    # Clean and tokenize query into keywords for filename matching
    words = re.findall(r"\b\w+\b", query.lower())
    stopwords = {
        "explain", "show", "summarize", "tell", "describe", "get", "retrieve",
        "my", "the", "a", "an", "is", "for", "of", "in", "on", "at", "by", "with",
        "about", "document", "file", "pdf", "docx", "txt", "sheet", "image",
        "me", "please", "can", "you", "what", "who", "where", "when", "how"
    }
    keywords = [w for w in words if w not in stopwords and len(w) > 2]

    # Fetch a larger candidate pool if we are applying score boosting for session or filename priority
    has_boosting = bool(session_id or keywords or selected_document_ids)
    fetch_limit = max(limit * 3, 15) if has_boosting else limit

    results = await qdrant_client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=fetch_limit,
    )

    if has_boosting:
        selected_document_ids_set = {str(d) for d in selected_document_ids} if selected_document_ids else set()
        boosted_points = []
        for hit in results.points:
            score = hit.score if hit.score is not None else 0.0
            
            # Apply session boost (+0.15)
            point_session_id = hit.payload.get("session_id")
            if session_id and point_session_id == str(session_id):
                score += 0.15

            # Apply filename keyword match boost (+0.20)
            filename = hit.payload.get("filename")
            filename_match = False
            if filename and keywords:
                filename_clean = filename.lower().rsplit(".", 1)[0]
                if any(kw in filename_clean for kw in keywords):
                    score += 0.20
                    filename_match = True

            # Apply selected document similarity boost (+0.40)
            point_doc_id = hit.payload.get("document_id")
            if selected_document_ids and point_doc_id and point_doc_id in selected_document_ids_set:
                doc_similar = filename_match
                if not doc_similar:
                    text = hit.payload.get("text")
                    if text and keywords:
                        text_clean = text.lower()
                        if any(kw in text_clean for kw in keywords):
                            doc_similar = True
                if doc_similar:
                    score += 0.40

            boosted_points.append((hit, score))
        
        # Sort by boosted score descending
        boosted_points.sort(key=lambda x: x[1], reverse=True)
        selected_points = [item[0] for item in boosted_points[:limit]]
    else:
        selected_points = results.points[:limit]

    return [
        {
            "text": hit.payload.get("text", ""),
            "filename": hit.payload.get("filename", "Unknown"),
            "document_id": hit.payload.get("document_id", ""),
        }
        for hit in selected_points
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
