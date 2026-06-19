"""
app/ai — Canonical AI / ML Module.

[Refactoring Note]:
This module has been refactored using a Domain-Driven Design (Vertical Slicing) approach.
All AI-related logic (LLM streaming, embeddings, RAG retrieval, vector storage, document
extraction) has been consolidated here to establish a single source of truth and to
prepare for eventual extraction into a standalone AI microservice.

Public API (Other modules MUST import only from here, never from internal sub-packages):
  # LLM
  chat_stream        — Async generator that yields LLM tokens
  summarize_text     — One-shot text summarization via LLM

  # Embeddings
  get_embedding      — Generate a text embedding vector

  # Vector storage (Qdrant)
  init_qdrant_collection    — Called once at startup
  store_document_vectors    — Chunk, embed, and upsert a document
  search_relevant_chunks    — Semantic search filtered by user
  delete_document_vectors   — Remove vectors for a document

  # RAG convenience wrappers
  ingest_document           — Wrapper around store_document_vectors
  retrieve_chunks           — Wrapper around search_relevant_chunks
  delete_document_chunks    — Wrapper around delete_document_vectors

  # Document text extraction
  extract_text              — Extract plain text from files (via AI service)
"""
from app.ai.services.vector_service import (
    init_qdrant_collection,
    search_relevant_chunks,
    store_document_vectors,
    delete_document_vectors,
)
from app.ai.services.llm_service import chat_stream, get_embedding, summarize_text
from app.ai.services.rag_service import (
    ingest_document,
    retrieve_chunks,
    delete_document_chunks,
)
from app.ai.services.document_service import extract_text
from app.ai.api.chat import router as chat_router
from app.ai.client import AIClient, get_ai_client
from app.ai.local_client import LocalAIClient
from app.ai.remote_client import RemoteAIClient

__all__ = [
    # Router
    "chat_router",
    # Client protocol and implementations
    "AIClient",
    "get_ai_client",
    "LocalAIClient",
    "RemoteAIClient",
    # LLM
    "chat_stream",
    "summarize_text",
    # Embeddings
    "get_embedding",
    # Vector storage
    "init_qdrant_collection",
    "store_document_vectors",
    "search_relevant_chunks",
    "delete_document_vectors",
    # RAG
    "ingest_document",
    "retrieve_chunks",
    "delete_document_chunks",
    # Document extraction
    "extract_text",
]
