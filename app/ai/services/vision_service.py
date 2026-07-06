"""
Vision service — in-memory visual extraction, downscaling, and Ollama vision inference.

This service is optimized to run on low-VRAM GPUs:
- Compresses and resizes image payloads to prevent GPU OOM crashes.
- Emits prompt VRAM unload parameters to Ollama (keep_alive: 10s).
- Extracts and processes visual sub-assets entirely in memory.
"""
from __future__ import annotations

import base64
import io
import logging
import httpx
import fitz  # PyMuPDF
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


def process_and_compress_image(image_bytes: bytes, max_size: int = 960) -> bytes:
    """
    Downscale and compress raw image bytes entirely in memory.
    Resizes the longest edge to max_size and saves as JPEG (quality=80).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert transparent/palette modes to RGB for JPEG formatting
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize if dimensions exceed max_size boundary
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=80)
        return out_io.getvalue()
    except Exception as exc:
        logger.error("Failed to resize/compress image in-memory: %s", exc)
        return image_bytes


def extract_visuals_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract embedded images and render pages with low text density as layout images.
    Returns:
        list[dict]: List of visual items: [{"base64_image": str, "page_number": int}]
    """
    visuals: list[dict] = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.error("Failed to open PDF %s for image extraction: %s", pdf_path, exc)
        return []

    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            text = page.get_text()

            # 1. Slide or visual-heavy page layout check (< 150 characters of text)
            if len(text.strip()) < 150:
                try:
                    # Render whole page at 150 DPI
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("jpeg")
                    compressed = process_and_compress_image(img_data)
                    b64_str = base64.b64encode(compressed).decode("utf-8")
                    visuals.append({
                        "base64_image": b64_str,
                        "page_number": page_num + 1
                    })
                    # Skip sub-image extraction for pages rendered as a whole
                    continue
                except Exception as e:
                    logger.warning(
                        "Failed to render slide/visual page %d of PDF %s: %s",
                        page_num + 1, pdf_path, e
                    )

            # 2. Extract embedded images on text-heavy pages
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Filter out small visual elements (icons, logos, decorative lines)
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    if width < 80 or height < 80 or len(image_bytes) < 5000:
                        continue

                    compressed = process_and_compress_image(image_bytes)
                    b64_str = base64.b64encode(compressed).decode("utf-8")
                    visuals.append({
                        "base64_image": b64_str,
                        "page_number": page_num + 1
                    })
                except Exception as e:
                    logger.warning(
                        "Failed to extract sub-image %d on page %d of PDF %s: %s",
                        img_idx, page_num + 1, pdf_path, e
                    )
        except Exception as exc:
            logger.warning("Failed processing page %d of PDF %s: %s", page_num + 1, pdf_path, exc)

    return visuals


async def describe_image(base64_image: str) -> str:
    """
    Call local Ollama vision model to describe the base64 encoded image.
    Uses keep_alive="10s" to release VRAM quickly.
    """
    prompt = (
        "Provide a structured description of this image. Follow these guidelines based on the image type:\n\n"
        "- If the image contains a complex diagram, flowchart, graph, architecture, or map:\n"
        "  Provide a highly detailed analysis. Explain the visual layout, nodes, connections (e.g., 'A points to B'), "
        "  data points, axes, legends, and transcribe all labels and numbers exactly as they appear.\n"
        "- Otherwise (e.g., standard photos, drawings, text documents, or simple illustrations):\n"
        "  Provide a detailed summary and extract the key details and text, keeping the explanation clean and concise.\n\n"
        "Your response should follow this structure:\n"
        "1. Summary: A clear overview of what the image represents.\n"
        "2. Visual Layout & Details: Describe the diagrams, layout, or visual elements (if applicable).\n"
        "3. Text & Data Extraction: Transcribe visible titles, headers, labels, and key text exactly as they appear.\n\n"
        "Ensure the description is structured and under 1000 words in total."
    )

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_vision_model,
                    "prompt": prompt,
                    "images": [base64_image],
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 4096,
                    },
                    "keep_alive": "10s",
                }
            )
            response.raise_for_status()
            res_data = response.json()
            desc = res_data.get("response", "").strip()
            if not desc:
                desc = res_data.get("thinking", "").strip()
            return desc
        except Exception as exc:
            logger.error(
                "Ollama vision inference failed using model %s: %s",
                settings.ollama_vision_model, exc
            )
            raise exc


async def reinspect_page(pdf_path: str, page_number: int, specific_question: str) -> str:
    """
    Open the original PDF, render page_number in-memory, compress it,
    and ask qwen3-vl:2b for the specific visual details.
    """
    print(f"\n[Vision AI] Re-inspecting page {page_number} of PDF '{pdf_path}' for question: '{specific_question}'...")
    try:
        doc = fitz.open(pdf_path)
        # page_number is 1-indexed
        page = doc[page_number - 1]

        # Render the page as image bytes at 150 DPI
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("jpeg")

        # Compress and encode
        compressed = process_and_compress_image(img_bytes)
        b64_str = base64.b64encode(compressed).decode("utf-8")

        prompt = (
            f"Look at this document page. Answer the following question based on the visual contents, "
            f"charts, tables, or equations: {specific_question}"
        )

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_vision_model,
                    "prompt": prompt,
                    "images": [b64_str],
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 4096,
                    },
                    "keep_alive": "10s",
                }
            )
            response.raise_for_status()
            res_data = response.json()
            desc = res_data.get("response", "").strip()
            if not desc:
                desc = res_data.get("thinking", "").strip()
            print(f"[Vision AI] Page {page_number} re-inspected successfully!")
            return desc
    except Exception as exc:
        print(f"[Vision AI] Failed to reinspect page {page_number}: {exc}")
        logger.error(
            "Failed to reinspect PDF page %d for document %s: %s",
            page_number, pdf_path, exc
        )
        raise exc
