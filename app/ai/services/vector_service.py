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
    MatchText,
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


async def _ensure_payload_indexes() -> None:
    """
    Best-effort payload indexes used by RAG filters and keyword retrieval.

    Qdrant raises if an index already exists on some versions, so each index is
    created independently and duplicate/existing-index errors are intentionally
    ignored.
    """
    index_specs = [
        (
            "text",
            TextIndexParams(
                type="text",
                tokenizer=TokenizerType.MULTILINGUAL,
                lowercase=True,
            ),
        ),
        (
            "filename",
            TextIndexParams(
                type="text",
                tokenizer=TokenizerType.MULTILINGUAL,
                lowercase=True,
            ),
        ),
        ("user_id", PayloadSchemaType.KEYWORD),
        ("session_id", PayloadSchemaType.KEYWORD),
        ("document_id", PayloadSchemaType.KEYWORD),
    ]

    for field_name, field_schema in index_specs:
        try:
            await qdrant_client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field_name,
                field_schema=field_schema,
            )
        except Exception as exc:
            logger.debug(
                "Payload index on '%s' was not created, likely already exists: %s",
                field_name,
                exc,
            )


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

            await _ensure_payload_indexes()
            logger.info("Payload indexes created for RAG retrieval.")
        else:
            logger.info("Qdrant collection '%s' already exists.", settings.qdrant_collection)
            await _ensure_payload_indexes()
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
    chunk_size: int = 1500,
    overlap: int = 200,
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
    await init_qdrant_collection()
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


async def store_image_vectors(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    image_metadata: list[dict],
    session_id: uuid.UUID | None = None,
) -> int:
    """
    Generate descriptions for each image, generate their embeddings,
    and store them in Qdrant.
    
    image_metadata: list[dict] where each item is {"base64_image": str, "page_number": int}
    """
    await init_qdrant_collection()
    from app.ai.services.vision_service import describe_image

    if not image_metadata:
        return 0

    points: list[PointStruct] = []

    for idx, meta in enumerate(image_metadata):
        b64 = meta["base64_image"]
        page_num = meta["page_number"]

        try:
            print(f"\n[Vision AI] Page {page_num}: Sending image to Ollama ({settings.ollama_vision_model}) for visual description...")
            description = await describe_image(b64)
            if not description:
                print(f"[Vision AI] Page {page_num}: Received empty description from model.")
                continue

            print(f"[Vision AI] Page {page_num}: Description generated successfully! Chunking and embedding...")
            formatted_text = f"[Image Description - Page {page_num}]: {description}"
            chunks = chunk_text(formatted_text, chunk_size=3000, overlap=300)
            print(f"[Vision AI] Page {page_num}: Split description into {len(chunks)} chunks. Storing in Qdrant...")

            for chunk_idx, chunk in enumerate(chunks):
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
                            "chunk_index": chunk_idx + 10000,  # Offset to prevent index collision
                            "type": "image_description",
                            "page_number": page_num,
                        },
                    )
                )
            print(f"[Vision AI] Page {page_num}: Chunks queued for Qdrant storage.")
        except Exception as exc:
            print(f"[Vision AI] Page {page_num}: Error processing image: {exc}")
            logger.error(
                "Failed to process and store image vector for page %d of document %s: %s",
                page_num,
                document_id,
                exc,
            )

    if points:
        print(f"[Vision AI] Upserting {len(points)} total vectors to Qdrant collection ({settings.qdrant_collection})...")
        await qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
        )
        print("[Vision AI] Qdrant upsert completed successfully!")
        logger.info(
            "Stored %d visual description vectors for document %s (user %s).",
            len(points),
            document_id,
            user_id,
        )
        return len(points)

    return 0


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _query_keywords(query: str) -> list[str]:
    words = re.findall(r"\b\w+\b", query.lower())
    stopwords = {
        "explain", "show", "summarize", "tell", "describe", "get", "retrieve",
        "my", "the", "a", "an", "is", "for", "of", "in", "on", "at", "by", "with",
        "about", "document", "file", "pdf", "docx", "txt", "sheet", "image",
        "me", "please", "can", "you", "what", "who", "where", "when", "how"
    }
    return [w for w in words if w not in stopwords and len(w) > 2]


def _build_base_filter(
    user_id: uuid.UUID,
    allowed_document_ids: list[uuid.UUID] | None = None,
    extra_conditions: list[FieldCondition] | None = None,
) -> Filter:
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

    if extra_conditions:
        must_conditions.extend(extra_conditions)

    return Filter(must=must_conditions)


def _keyword_score(payload: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.0

    text = (payload.get("text") or "").lower()
    filename = (payload.get("filename") or "").lower()
    searchable = f"{filename} {text}"

    matches = sum(1 for keyword in keywords if keyword in searchable)
    if matches == 0:
        return 0.0

    score = matches / len(keywords)
    if any(keyword in filename for keyword in keywords):
        score += 0.25
    return min(score, 1.0)


def _boosted_score(
    payload: dict,
    base_score: float,
    keywords: list[str],
    session_id: uuid.UUID | None = None,
    selected_document_ids: list[uuid.UUID] | None = None,
) -> float:
    score = base_score

    point_session_id = payload.get("session_id")
    if session_id and point_session_id == str(session_id):
        score += 0.15

    filename = (payload.get("filename") or "").lower().rsplit(".", 1)[0]
    filename_match = bool(filename and keywords and any(kw in filename for kw in keywords))
    if filename_match:
        score += 0.20

    point_doc_id = payload.get("document_id")
    selected_document_ids_set = {str(d) for d in selected_document_ids} if selected_document_ids else set()
    if selected_document_ids and point_doc_id and point_doc_id in selected_document_ids_set:
        text = (payload.get("text") or "").lower()
        content_match = bool(keywords and any(kw in text for kw in keywords))
        if filename_match or content_match:
            score += 0.40

    return score


def _result_key(payload: dict) -> tuple[str, int]:
    return (
        str(payload.get("document_id") or ""),
        int(payload.get("chunk_index") or 0),
    )


def _format_result(payload: dict, score: float, match_type: str) -> dict:
    return {
        "text": payload.get("text", ""),
        "filename": payload.get("filename", "Unknown"),
        "document_id": payload.get("document_id", ""),
        "score": round(score, 6),
        "match_type": match_type,
    }


async def generate_hypothetical_document(query: str) -> str:
    """
    Generate a concise hypothetical passage for HyDE retrieval.

    The generated text is used only as the semantic search query. The user's
    original question remains the source of truth for keyword search, reranking,
    and final answer generation.
    """
    prompt = (
        "Write a concise factual passage that could answer the user's question. "
        "Do not use markdown, citations, bullet points, or claims of certainty. "
        "Do not mention that the passage is hypothetical. "
        "Keep it under 120 words.\n\n"
        f"Question: {query}\n\n"
        "Passage:"
    )

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


async def _semantic_candidates(
    user_id: uuid.UUID,
    query: str,
    limit: int,
    allowed_document_ids: list[uuid.UUID] | None,
) -> list[tuple[dict, float]]:
    query_vector = await get_ollama_embedding(query, prefix_type="query")
    results = await qdrant_client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=_build_base_filter(user_id, allowed_document_ids),
        limit=limit,
    )
    return [
        (hit.payload or {}, hit.score if hit.score is not None else 0.0)
        for hit in results.points
    ]


async def _keyword_candidates(
    user_id: uuid.UUID,
    query: str,
    keywords: list[str],
    limit: int,
    allowed_document_ids: list[uuid.UUID] | None,
) -> list[tuple[dict, float]]:
    if not keywords:
        return []

    seen: dict[tuple[str, int], tuple[dict, float]] = {}
    search_terms = [query] + keywords[:6]

    for term in search_terms:
        text_condition = FieldCondition(
            key="text",
            match=MatchText(text=term),
        )
        filename_condition = FieldCondition(
            key="filename",
            match=MatchText(text=term),
        )

        for condition in (text_condition, filename_condition):
            try:
                points, _ = await qdrant_client.scroll(
                    collection_name=settings.qdrant_collection,
                    scroll_filter=_build_base_filter(
                        user_id,
                        allowed_document_ids,
                        extra_conditions=[condition],
                    ),
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception as exc:
                logger.debug("Keyword candidate search failed for term '%s': %s", term, exc)
                continue

            for point in points:
                payload = point.payload or {}
                key = _result_key(payload)
                score = _keyword_score(payload, keywords)
                previous = seen.get(key)
                if previous is None or score > previous[1]:
                    seen[key] = (payload, score)

    return sorted(seen.values(), key=lambda item: item[1], reverse=True)[:limit]


async def search_relevant_chunks(
    user_id: uuid.UUID,
    query: str,
    limit: int = 4,
    retrieval_mode: str = "semantic",
    use_hyde: bool = False,
    allowed_document_ids: list[uuid.UUID] | None = None,
    session_id: uuid.UUID | None = None,
    selected_document_ids: list[uuid.UUID] | None = None,
    use_reranker: bool = False,
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
    await init_qdrant_collection()
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    retrieval_mode = retrieval_mode.lower()
    if retrieval_mode not in {"semantic", "keyword", "hybrid"}:
        retrieval_mode = "semantic"

    keywords = _query_keywords(query)
    has_boosting = bool(session_id or keywords or selected_document_ids)
    candidate_limit = max(limit * 4, 25) if (has_boosting or retrieval_mode == "hybrid" or use_reranker) else limit

    candidates: dict[tuple[str, int], dict] = {}
    semantic_query = query

    if use_hyde and retrieval_mode in {"semantic", "hybrid"}:
        try:
            hypothetical_document = await generate_hypothetical_document(query)
            if hypothetical_document:
                semantic_query = hypothetical_document
        except Exception as exc:
            logger.warning(
                "HyDE generation failed; falling back to original query: %s",
                exc,
                exc_info=settings.debug,
            )

    semantic_results = []
    if retrieval_mode in {"semantic", "hybrid"}:
        semantic_results = await _semantic_candidates(
            user_id=user_id,
            query=semantic_query,
            limit=candidate_limit,
            allowed_document_ids=allowed_document_ids,
        )
        for payload, semantic_score in semantic_results:
            key = _result_key(payload)
            candidates[key] = {
                "payload": payload,
                "semantic_score": semantic_score,
                "keyword_score": _keyword_score(payload, keywords),
            }

    keyword_results = []
    if retrieval_mode in {"keyword", "hybrid"}:
        keyword_results = await _keyword_candidates(
            user_id=user_id,
            query=query,
            keywords=keywords,
            limit=candidate_limit,
            allowed_document_ids=allowed_document_ids,
        )
        for payload, keyword_score in keyword_results:
            key = _result_key(payload)
            existing = candidates.get(key)
            if existing:
                existing["keyword_score"] = max(existing["keyword_score"], keyword_score)
            else:
                candidates[key] = {
                    "payload": payload,
                    "semantic_score": 0.0,
                    "keyword_score": keyword_score,
                }

    if retrieval_mode == "keyword" and not candidates:
        return []

    # Map candidate keys to their rank index (1-based)
    semantic_ranks = {
        _result_key(payload): rank
        for rank, (payload, _) in enumerate(semantic_results, start=1)
    }
    keyword_ranks = {
        _result_key(payload): rank
        for rank, (payload, _) in enumerate(keyword_results, start=1)
    }

    reranked = []
    if use_reranker and candidates:
        from app.ai.services.reranker_service import rerank_candidates
        import math

        # Prepare candidates for reranking
        items_to_rerank = []
        for key, item in candidates.items():
            payload = item["payload"]
            semantic_score = item["semantic_score"]
            keyword_score = item["keyword_score"]

            match_type = retrieval_mode
            if retrieval_mode == "hybrid":
                if semantic_score and keyword_score:
                    match_type = "hybrid"
                elif semantic_score:
                    match_type = "semantic"
                else:
                    match_type = "keyword"
            
            items_to_rerank.append({
                "key": key,
                "text": payload.get("text", ""),
                "payload": payload,
                "match_type": match_type,
            })

        # Run model inference (thread-safe, does not block event loop)
        reranked_items = await rerank_candidates(query, items_to_rerank)

        for item in reranked_items:
            payload = item["payload"]
            match_type = item["match_type"]
            logit_score = item["rerank_score"]

            # Map raw logit score to [0, 1] using Sigmoid
            try:
                sigmoid_score = 1.0 / (1.0 + math.exp(-logit_score))
            except OverflowError:
                sigmoid_score = 0.0 if logit_score < 0 else 1.0

            final_score = _boosted_score(
                payload=payload,
                base_score=sigmoid_score,
                keywords=keywords,
                session_id=session_id,
                selected_document_ids=selected_document_ids,
            )
            reranked.append((payload, final_score, match_type))
    else:
        # Standard scoring path (RRF / Semantic / Keyword)
        for key, item in candidates.items():
            payload = item["payload"]
            semantic_score = item["semantic_score"]
            keyword_score = item["keyword_score"]

            if retrieval_mode == "hybrid":
                r_sem = semantic_ranks.get(key)
                r_key = keyword_ranks.get(key)
                
                score_sem = 1.0 / (60.0 + r_sem) if r_sem else 0.0
                score_key = 1.0 / (60.0 + r_key) if r_key else 0.0
                
                # Normalize RRF base score to [0, 1] range to match scale of boosts.
                # Max possible score is 1/61 + 1/61 = 2/61. Multiply by 30.5 to normalize.
                base_score = (score_sem + score_key) * 30.5
            elif retrieval_mode == "keyword":
                base_score = keyword_score
            else:
                base_score = semantic_score

            final_score = _boosted_score(
                payload=payload,
                base_score=base_score,
                keywords=keywords,
                session_id=session_id,
                selected_document_ids=selected_document_ids,
            )
            match_type = retrieval_mode
            if retrieval_mode == "hybrid":
                if semantic_score and keyword_score:
                    match_type = "hybrid"
                elif semantic_score:
                    match_type = "semantic"
                else:
                    match_type = "keyword"
            reranked.append((payload, final_score, match_type))

    reranked.sort(key=lambda item: item[1], reverse=True)

    return [
        _format_result(payload, score, match_type)
        for payload, score, match_type in reranked[:limit]
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
    await init_qdrant_collection()
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
