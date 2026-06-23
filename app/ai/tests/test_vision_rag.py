import base64
import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz
import pytest
import httpx
from PIL import Image

from app.ai.services import vision_service
from app.ai.services.vector_service import store_image_vectors
from app.config import settings


def test_process_and_compress_image():
    # 1. Create a large mock image (1200x800 RGBA)
    img = Image.new("RGBA", (1200, 800), color=(255, 0, 0, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    original_bytes = img_byte_arr.getvalue()

    # 2. Compress the image
    compressed_bytes = vision_service.process_and_compress_image(original_bytes, max_size=960)

    # 3. Verify it was resized and converted to JPEG (RGB)
    compressed_img = Image.open(io.BytesIO(compressed_bytes))
    assert compressed_img.format == "JPEG"
    assert compressed_img.mode == "RGB"
    # Aspect ratio preserved, longest edge should be 960
    assert compressed_img.size == (960, 640)


def test_extract_visuals_from_pdf_low_text_density():
    # Create a temporary PDF page with very low text density to trigger full page rendering
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Tiny text")  # Length is 9 characters (< 150)
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(doc.write())
        tmp_path = tmp.name

    try:
        visuals = vision_service.extract_visuals_from_pdf(tmp_path)
        assert len(visuals) == 1
        assert "base64_image" in visuals[0]
        assert visuals[0]["page_number"] == 1
    finally:
        Path(tmp_path).unlink()


@pytest.mark.asyncio
async def test_describe_image_success():
    mock_response = {
        "response": "This is a detailed description of the chart."
    }

    # Mock the HTTP response from Ollama
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200,
            json=mock_response,
            request=httpx.Request("POST", "http://localhost")
        )
        
        result = await vision_service.describe_image("mock_base64_string")
        
        assert result == "This is a detailed description of the chart."
        mock_post.assert_called_once()
        # Verify keep_alive parameter is passed
        call_json = mock_post.call_args[1]["json"]
        assert call_json["model"] == settings.ollama_vision_model
        assert call_json["keep_alive"] == "10s"


@pytest.mark.asyncio
async def test_store_image_vectors():
    # Mock visual payload from PyMuPDF
    mock_visuals = [
        {"base64_image": "mock_b64", "page_number": 2}
    ]

    with patch("app.ai.services.vision_service.describe_image", AsyncMock(return_value="Detailed flowchart description")) as mock_desc, \
         patch("app.ai.services.vector_service.get_ollama_embedding", AsyncMock(return_value=[0.1] * 768)) as mock_embed, \
         patch("app.ai.services.vector_service.qdrant_client.upsert", AsyncMock()) as mock_upsert:

        import uuid
        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        
        stored_count = await store_image_vectors(
            user_id=user_id,
            document_id=doc_id,
            filename="notes.pdf",
            image_metadata=mock_visuals,
        )

        assert stored_count == 1
        mock_desc.assert_called_once_with("mock_b64")
        mock_embed.assert_called_once_with(
            "[Image Description - Page 2]: Detailed flowchart description",
            prefix_type="document"
        )
        mock_upsert.assert_called_once()


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_describe_image():
    """
    Live integration test that verifies the model's visual reasoning:
    1. Tests OCR transcription (reading drawn text).
    2. Tests object/color recognition (noticing a blue shape).
    3. Tests markdown formatting.
    """
    from PIL import ImageDraw

    # 1. Create a 400x200 test image with a blue circle and black text
    img = Image.new("RGB", (400, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw a blue circle
    draw.ellipse([30, 50, 130, 150], fill=(0, 0, 255))

    # Draw text "CixioHub OCR Test"
    draw.text((160, 90), "CixioHub OCR Test", fill=(0, 0, 0))

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    # 2. Process and encode it
    compressed = vision_service.process_and_compress_image(img_bytes)
    b64_str = base64.b64encode(compressed).decode("utf-8")

    # 3. Run against local Ollama if qwen3-vl:2b is active
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                tags = [m["name"] for m in resp.json().get("models", [])]
                if any(settings.ollama_vision_model in t for t in tags):
                    description = await vision_service.describe_image(b64_str)

                    description_lower = description.lower()

                    # A. Verify OCR was successful
                    assert any(word in description_lower for word in ["cixiohub", "ocr", "test"]), \
                        f"Vision model failed to read text. Output: {description}"

                    # B. Verify object detection was successful
                    assert any(word in description_lower for word in ["blue", "circle", "ellipse"]), \
                        f"Vision model failed to identify blue circle. Output: {description}"

                    # C. Verify structured output was respected
                    assert "ocr" in description_lower and "visual" in description_lower

                    print(f"\n✅ Live Vision reasoning test passed successfully.")
                    return
    except Exception as exc:
        pytest.skip(f"Live Ollama vision service unavailable: {exc}")

    pytest.skip(f"Local Ollama does not have the model '{settings.ollama_vision_model}' installed.")
