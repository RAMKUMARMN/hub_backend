from __future__ import annotations

import json
import uuid
import httpx
from typing import AsyncIterator

from app.ai.client import AIClient
from app.config import settings

class RemoteAIClient(AIClient):
    """
    Remote implementation of AIClient that proxies all AI requests via HTTP
    to a separate AI microservice (settings.ai_service_url).
    """

    def _get_client(self, timeout: float = 60.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=settings.ai_service_url, timeout=timeout)

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
    ) -> AsyncIterator[str]:
        in_thinking = False
        async with self._get_client(timeout=300.0) as client:
            async with client.stream("POST", "/api/v1/chat/stream", json={"messages": messages, "think": think}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            payload = json.loads(data_str)
                            if "thinking" in payload and payload["thinking"]:
                                if not in_thinking:
                                    in_thinking = True
                                    yield "<think>"
                                yield payload["thinking"]
                            elif "delta" in payload and payload["delta"]:
                                if in_thinking:
                                    in_thinking = False
                                    yield "</think>"
                                yield payload["delta"]
                        except json.JSONDecodeError:
                            pass
                # Close any open thinking block
                if in_thinking:
                    yield "</think>"

    async def summarize_text(
        self,
        text: str,
    ) -> str:
        async with self._get_client() as client:
            response = await client.post("/api/v1/chat/summarize", json={"text": text})
            response.raise_for_status()
            return response.json()["summary"]

    async def get_embedding(
        self,
        text: str,
    ) -> list[float]:
        async with self._get_client() as client:
            response = await client.post("/api/v1/embeddings", json={"text": text})
            response.raise_for_status()
            return response.json()["embedding"]

    async def store_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        text: str,
        filename: str = "",
        session_id: uuid.UUID | None = None,
    ) -> int:
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/documents/ingest",
                json={
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    "text": text,
                    "filename": filename,
                    "session_id": str(session_id) if session_id else None,
                },
            )
            response.raise_for_status()
            return response.json()["chunks_stored"]

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool = True,
    ) -> dict:
        """One-shot chat completion with support for tool/function calling."""
        async with self._get_client(timeout=300.0) as client:
            response = await client.post(
                "/api/v1/chat/tools",
                json={
                    "messages": messages,
                    "tools": tools,
                    "think": think,
                },
            )
            response.raise_for_status()
            return response.json()["message"]

    async def store_image_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        image_metadata: list[dict],
        session_id: uuid.UUID | None = None,
    ) -> int:
        """Process, describe, embed, and store image vectors for a document."""
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/documents/ingest_images",
                json={
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    "filename": filename,
                    "image_metadata": image_metadata,
                    "session_id": str(session_id) if session_id else None,
                },
            )
            response.raise_for_status()
            res_data = response.json()
            return res_data.get("chunks_stored") or res_data.get("images_stored") or 0

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
        async with self._get_client() as client:
            response = await client.post(
                "/api/v1/documents/search",
                json={
                    "user_id": str(user_id),
                    "query": query,
                    "limit": limit,
                    "retrieval_mode": retrieval_mode,
                    "use_hyde": use_hyde,
                    "allowed_document_ids": [str(d) for d in allowed_document_ids] if allowed_document_ids else None,
                    "session_id": str(session_id) if session_id else None,
                    "selected_document_ids": [str(d) for d in selected_document_ids] if selected_document_ids else None,
                    "use_reranker": use_reranker,
                    "include_meta": include_meta,
                },
            )
            response.raise_for_status()
            return response.json()["results"]

    async def delete_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        async with self._get_client() as client:
            response = await client.request(
                "DELETE",
                f"/api/v1/documents/{document_id}",
                params={"user_id": str(user_id)},
            )
            response.raise_for_status()

    async def extract_text(
        self,
        file_path: str,
        file_type: str,
    ) -> str:
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/extract",
                json={"file_path": file_path, "file_type": file_type},
            )
            response.raise_for_status()
            return response.json()["text"]

    async def web_search(
        self,
        query: str,
        max_results: int = 5,
    ) -> str:
        """Search the web via the AI microservice."""
        async with self._get_client(timeout=30.0) as client:
            response = await client.post(
                "/api/v1/web/search",
                json={"query": query, "max_results": max_results},
            )
            response.raise_for_status()
            return response.json()["result"]

    async def compress_image(self, image_bytes: bytes) -> str:
        """Compress raw image bytes via the AI microservice."""
        async with self._get_client(timeout=60.0) as client:
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
            response = await client.post(
                "/api/v1/vision/compress",
                files=files,
            )
            response.raise_for_status()
            return response.json()["base64_image"]

    async def extract_visuals_from_pdf(self, pdf_path: str) -> list[dict]:
        """Extract visuals from PDF via the AI microservice."""
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/vision/extract_visuals",
                json={"pdf_path": pdf_path},
            )
            response.raise_for_status()
            return response.json()["visuals"]

    async def reinspect_pdf_page(
        self,
        pdf_path: str,
        page_number: int,
        specific_question: str,
    ) -> str:
        """Ask vision model visual QA on a PDF page via the AI microservice."""
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/vision/reinspect",
                json={
                    "pdf_path": pdf_path,
                    "page_number": page_number,
                    "specific_question": specific_question,
                },
            )
            response.raise_for_status()
            return response.json()["description"]

    async def vision_qa_image(
        self,
        base64_image: str,
        question: str,
    ) -> str:
        """Ask vision model QA on a base64 image via the AI microservice."""
        async with self._get_client(timeout=120.0) as client:
            response = await client.post(
                "/api/v1/vision/qa",
                json={
                    "base64_image": base64_image,
                    "question": question,
                },
            )
            response.raise_for_status()
            return response.json()["description"]
