import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.ai.remote_client import RemoteAIClient
from app.config import settings

@pytest.mark.asyncio
async def test_remote_client_chat_with_tools():
    client = RemoteAIClient()
    messages = [{"role": "user", "content": "test"}]
    tools = [{"type": "function", "function": {"name": "test_tool"}}]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "tool output"}
    }

    # Patch httpx.AsyncClient.post to return mock_response
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response

        res = await client.chat_with_tools(messages=messages, tools=tools)

        assert res["content"] == "tool output"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["messages"] == messages
        assert call_kwargs["json"]["tools"] == tools
        assert "/api/v1/chat/tools" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_remote_client_store_image_vectors():
    client = RemoteAIClient()
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    filename = "test_image.png"
    image_metadata = [{"base64_image": "abc", "page_number": 1}]
    session_id = uuid.uuid4()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "chunks_stored": 5
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response

        stored = await client.store_image_vectors(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            image_metadata=image_metadata,
            session_id=session_id,
        )

        assert stored == 5
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["user_id"] == str(user_id)
        assert call_kwargs["json"]["document_id"] == str(document_id)
        assert call_kwargs["json"]["filename"] == filename
        assert call_kwargs["json"]["image_metadata"] == image_metadata
        assert call_kwargs["json"]["session_id"] == str(session_id)
        assert "/api/v1/documents/ingest_images" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_remote_client_search_relevant_chunks():
    client = RemoteAIClient()
    user_id = uuid.uuid4()
    query = "rerank search"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [{"text": "matching content", "filename": "doc.txt"}]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response

        results = await client.search_relevant_chunks(
            user_id=user_id,
            query=query,
            use_reranker=True,
        )

        assert len(results) == 1
        assert results[0]["filename"] == "doc.txt"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["user_id"] == str(user_id)
        assert call_kwargs["json"]["query"] == query
        assert call_kwargs["json"]["use_reranker"] is True
        assert "/api/v1/documents/search" in mock_post.call_args[0][0]
