"""
app/ai — AI Integration Module.

All heavy AI/ML processing (LLM streaming, embeddings, RAG retrieval, vector
storage, reranking) runs in the standalone hub_ai microservice.

This module provides the thin client layer that the backend uses to communicate
with the microservice, plus the chat router that manages database-backed
conversation sessions.

Public API:
  chat_router       — FastAPI router for chat session CRUD and message streaming
  AIClient          — Abstract protocol defining the AI service interface
  get_ai_client     — Factory that returns the configured RemoteAIClient instance
  RemoteAIClient    — HTTP proxy that forwards requests to the AI microservice
"""
from app.ai.api.chat import router as chat_router
from app.ai.client import AIClient
from app.ai.dependencies import get_ai_client
from app.ai.remote_client import RemoteAIClient

__all__ = [
    "chat_router",
    "AIClient",
    "get_ai_client",
    "RemoteAIClient",
]
