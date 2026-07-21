"""
Document text extraction service — delegates to the AI service.

The AI service (cixio-hub/ai, port 8003) handles:
  - PDF extraction via PyMuPDF
  - DOCX extraction via python-docx
  - Plain text reading
  - Image OCR via Tesseract

Students (AI/LLM role): implement extraction in cixio-hub/ai/app/rag/document_extractor.py
Students (Backend role): this file is already wired.
"""

from __future__ import annotations

import httpx

from app.config import settings


async def extract_text(file_path: str, file_type: str) -> str:
    """
    Extract plain text from a file via the AI service.

    Args:
        file_path: Absolute path to the saved file (accessible to AI service)
        file_type: Extension without dot, e.g. 'pdf', 'docx', 'txt', 'png'

    Returns:
        Extracted plain text string.
    """
    async with httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=120
    ) as client:
        response = await client.post(
            "/api/v1/extract",
            json={"file_path": file_path, "file_type": file_type},
        )
        response.raise_for_status()
        return response.json()["text"]
