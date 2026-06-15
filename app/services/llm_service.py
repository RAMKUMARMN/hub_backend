"""
LLM service — direct Ollama streaming (no external AI microservice required).

Exposes a chat_stream() async generator that proxies messages to the local
Ollama /api/chat endpoint and yields individual token strings.

Also exposes get_embedding() as a thin convenience wrapper around
vector_service.get_ollama_embedding() for any code that still imports from here.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.services.vector_service import get_ollama_embedding  # re-export convenience

logger = logging.getLogger(__name__)


async def chat_stream(
    messages: list[dict],
    user_id: str,
    context_chunks: list[str] | None = None,
    use_rag: bool = False,
) -> AsyncIterator[str]:
    """
    Stream tokens directly from the local Ollama /api/chat endpoint.

    If context_chunks are provided (e.g. from RAG retrieval), they are
    injected into a system message prepended to the conversation.

    Yields individual token strings (unwrapped from Ollama's JSON lines).
    Raises httpx.ConnectError if Ollama is not reachable.
    """
    # Build the final message list; optionally prepend RAG context.
    if context_chunks:
        context_text = "\n\n".join(context_chunks)
        system_msg = {
            "role": "system",
            "content": (
                "Answer the user's question using the following context from "
                "their uploaded documents:\n\n"
                f"--- CONTEXT ---\n{context_text}\n----------------"
            ),
        }
        ollama_messages = [system_msg] + messages
    else:
        ollama_messages = messages

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": ollama_messages,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    token: str = parsed.get("message", {}).get("content", "")
                    if token:
                        yield token
                except (json.JSONDecodeError, KeyError):
                    continue


async def get_embedding(text: str) -> list[float]:
    """
    Convenience wrapper — returns a 768-dim embedding from nomic-embed-text.
    Delegates to vector_service.get_ollama_embedding().
    """
    return await get_ollama_embedding(text)
