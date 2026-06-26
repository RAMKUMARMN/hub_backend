"""
LLM service — proxies chat streaming requests to the AI service.

The AI service (cixio-hub/ai, port 8003) handles:
  - Ollama streaming
  - RAG context injection
  - Embedding generation

Students (AI/LLM role): implement the streaming logic in cixio-hub/ai.
Students (Backend role): this file is already wired — focus on chat.py router.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings


async def chat_stream(
    messages: list[dict],
    user_id: str,
    context_chunks: list[str] | None = None,
    use_rag: bool = False,
) -> AsyncIterator[str]:
    """
    Stream tokens from the AI service chat endpoint.

    The AI service at /api/v1/chat/stream handles:
      - Ollama SSE streaming
      - RAG context injection (if use_rag=True)

    Yields individual token strings.
    """
    payload = {
        "messages": messages,
        "user_id": user_id,
        "use_rag": use_rag,
    }

    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=120
    ) as client:
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                print("RAW DATA:", data)
                if data == "[DONE]":
                    return
                try:
                    parsed = json.loads(data)

                    delta = parsed.get("delta") or parsed.get("content", "")

                    if delta:
                        print("STREAM TOKEN:", delta)  # debug
                        yield delta
                except json.JSONDecodeError:
                    continue


async def get_embedding(text: str) -> list[float]:
    """Get a text embedding vector from the AI service."""
    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=60
    ) as client:
        response = await client.post("/api/v1/embed", json={"text": text})
        response.raise_for_status()
        return response.json()["embedding"]

