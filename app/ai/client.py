from __future__ import annotations

import uuid
from typing import Protocol, AsyncIterator


class AIClient(Protocol):
    """
    Contract for all AI operations required by the CixioHub backend.
    Enables swapping local service execution (Ollama/Qdrant) with remote microservice API proxy.
    """

    async def chat_stream(
        self,
        messages: list[dict],
        think: bool = True,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from LLM."""
        pass

    async def summarize_text(
        self,
        text: str,
    ) -> str:
        """Summarize conversational history/text using LLM."""
        pass

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool = True,
    ) -> dict:
        """One-shot chat completion with support for tool/function calling."""
        pass

    async def get_embedding(
        self,
        text: str,
    ) -> list[float]:
        """Generate a text embedding vector."""
        pass

    async def store_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        text: str,
        filename: str = "",
        session_id: uuid.UUID | None = None,
    ) -> int:
        """Chunk, embed, and upload document vectors to storage."""
        pass

    async def store_image_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        image_metadata: list[dict],
        session_id: uuid.UUID | None = None,
    ) -> int:
        """Process, describe, embed, and store image vectors for a document."""
        pass

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
        """Search relevant document chunks by query similarity."""
        pass

    async def delete_document_vectors(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        """Delete vector storage points for a document."""
        pass

    async def extract_text(
        self,
        file_path: str,
        file_type: str,
    ) -> str:
        """Extract text from a file (e.g. PDF/DOCX/OCR)."""
        pass

    async def web_search(
        self,
        query: str,
        max_results: int = 5,
    ) -> str:
        """Search the web and return formatted results."""
        pass

    async def compress_image(self, image_bytes: bytes) -> str:
        """Compress raw image bytes and return base64 encoded string."""
        pass

    async def extract_visuals_from_pdf(self, pdf_path: str) -> list[dict]:
        """Extract visual elements (images or rendered pages) from a PDF file."""
        pass

    async def reinspect_pdf_page(
        self,
        pdf_path: str,
        page_number: int,
        specific_question: str,
    ) -> str:
        """Render and ask vision model QA about a specific PDF page."""
        pass

    async def vision_qa_image(
        self,
        base64_image: str,
        question: str,
    ) -> str:
        """Ask a vision model QA about a base64 encoded image."""
        pass
