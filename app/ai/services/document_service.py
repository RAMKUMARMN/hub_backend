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

from pathlib import Path
import httpx

from app.config import settings


async def extract_text(file_path: str, file_type: str) -> str:
    """
    Extract plain text from a file.
    Attempts to extract locally for PDF, TXT, and MD files to avoid dependency on external service.
    Falls back to the external AI service if local extraction fails.
    """
    ft = file_type.lower().strip()
    content_bytes: bytes | None = None
    
    # 1. Retrieve the file content
    if file_path.startswith("http://") or file_path.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(file_path)
                resp.raise_for_status()
                content_bytes = resp.content
        except Exception:
            pass
    else:
        # Check local filesystem (try absolute path, then relative uploads directory path)
        for path_obj in (Path(file_path), Path("uploads") / file_path):
            if path_obj.exists() and path_obj.is_file():
                try:
                    content_bytes = path_obj.read_bytes()
                    break
                except Exception:
                    pass

    # 2. Try parsing the content bytes locally
    if content_bytes is not None:
        if ft in ("txt", "md"):
            try:
                return content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                pass
        elif ft == "pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=content_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except Exception:
                pass

    # 3. Fallback to external AI service on port 8003
    try:
        async with httpx.AsyncClient(
            base_url=settings.ai_service_url, timeout=120
        ) as client:
            response = await client.post(
                "/api/v1/extract",
                json={"file_path": file_path, "file_type": file_type},
            )
            response.raise_for_status()
            return response.json()["text"]
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "External AI service extraction failed for %s (type %s). Fallback to empty text. Error: %s",
            file_path,
            file_type,
            exc,
        )
        return ""
