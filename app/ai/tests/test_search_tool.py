import pytest
import pytest_asyncio
import uuid
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.database import AsyncSessionLocal
from app.ai.client import get_ai_client
from app.models.user import User
from app.auth.security.password import hash_password

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    from app.database import engine
    await engine.dispose()
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE;"))
        await session.execute(text("TRUNCATE TABLE chat_sessions CASCADE;"))
        await session.execute(text("TRUNCATE TABLE documents CASCADE;"))
        await session.commit()
    yield

@pytest_asyncio.fixture
async def authenticated_client(client):
    async with AsyncSessionLocal() as session:
        user = User(
            email="test_search@tkmce.ac.in",
            full_name="Search Tester",
            hashed_password=hash_password("securepassword123"),
            is_active=True,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test_search@tkmce.ac.in", "password": "securepassword123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

# ── Service unit tests ──

@pytest.mark.asyncio
async def test_search_tavily_success():
    from app.ai.services.search_service import search_tavily
    from app.config import settings
    
    settings.tavily_api_key = "fake_key"
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Test Title", "url": "https://test.com", "content": "Test Content"}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await search_tavily("test query")
        lines = result.splitlines()
        assert len(lines) >= 3
        assert lines[0] == "Source: https://test.com"
        assert lines[1] == "Title: Test Title"
        assert lines[2] == "Snippet: Test Content"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_search_tavily_missing_key():
    from app.ai.services.search_service import search_tavily
    from app.config import settings
    
    original_key = settings.tavily_api_key
    settings.tavily_api_key = None
    try:
        with pytest.raises(ValueError, match="Tavily API key is not configured"):
            await search_tavily("test")
    finally:
        settings.tavily_api_key = original_key

@pytest.mark.asyncio
async def test_unified_search_fallback():
    from app.ai.services.search_service import unified_web_search
    from app.config import settings
    
    settings.tavily_api_key = "fake_key"
    
    # We mock search_tavily to raise an exception, and search_duckduckgo to return mock DDG results
    with patch("app.ai.services.search_service.search_tavily", side_effect=Exception("Tavily Error")), \
         patch("app.ai.services.search_service.search_duckduckgo") as mock_ddg:
        
        mock_ddg.return_value = "DuckDuckGo: Result Found"
        
        result = await unified_web_search("fallback test")
        assert result == "DuckDuckGo: Result Found"
        mock_ddg.assert_called_once_with("fallback test", max_results=5)

# ── End-to-end Chat integration test ──

@pytest.mark.asyncio
async def test_chat_triggers_web_search_tool(authenticated_client):
    from app.config import settings
    
    # Enable web search setting
    original_search_setting = settings.enable_web_search
    settings.enable_web_search = True
    
    # 1. Create a chat session
    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Search Session"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])
    
    # 2. Setup mock AI client that decides to call web search
    class FakeAIClient:
        def __init__(self):
            self.calls = 0
            
        async def chat_with_tools(self, messages, tools=None, think=True):
            self.calls += 1
            if self.calls == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_search_123",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": {
                                    "query": "Ethereum price today"
                                }
                            }
                        }
                    ]
                }
            else:
                has_search_msg = any(msg.get("role") == "tool" and "Ethereum price is $3000" in msg.get("content") for msg in messages)
                if has_search_msg:
                    content = "The price of Ethereum today is $3000 according to search results."
                else:
                    content = "Unable to fetch search results."
                return {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": None
                }

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai
    
    # 3. Mock the search service execution
    with patch("app.ai.services.search_service.unified_web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "Source: https://crypto.com\nTitle: Price\nSnippet: Ethereum price is $3000 today."
        
        try:
            # Send message triggers search
            response = await authenticated_client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={
                    "content": "What is the price of Ethereum today?",
                    "use_rag": False,
                    "web_search": True
                }
            )
            assert response.status_code == 200
            
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    events.append(json.loads(data_str))
                    
            full_text = "".join(ev.get("delta", "") for ev in events if "delta" in ev)
            assert "$3000" in full_text
            
            mock_search.assert_called_once_with("Ethereum price today", max_results=5)
            assert fake_ai.calls == 2
            
        finally:
            app.dependency_overrides.pop(get_ai_client, None)
            settings.enable_web_search = original_search_setting


# ── Live end-to-end test (requires running Ollama + internet access) ──

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_duckduckgo_fallback_end_to_end(authenticated_client):
    """
    Live integration test: sends a real-time query to a running Ollama instance
    with web search enabled but Tavily key cleared. Verifies that DuckDuckGo
    fallback works correctly as the backup search engine.

    Requires:
      - Ollama running locally with a model that supports tool calling
      - Internet access for DuckDuckGo scraping
      - Run with: pytest -m live
    """
    from app.config import settings

    # Save originals
    original_search = settings.enable_web_search
    original_tavily_key = settings.tavily_api_key

    # Force web search ON and Tavily OFF (so it falls back to DuckDuckGo)
    settings.enable_web_search = True
    settings.tavily_api_key = None

    try:
        # 1. Create a chat session
        session_resp = await authenticated_client.post(
            "/api/v1/chat/sessions",
            json={"title": "Live Search Test"}
        )
        assert session_resp.status_code == status.HTTP_201_CREATED
        session_id = session_resp.json()["id"]

        # 2. Send a real-time query that should trigger web search
        msg_resp = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "What is the current price of Bitcoin today?",
                "use_rag": False,
                "web_search": True
            },
            timeout=120.0
        )
        assert msg_resp.status_code == 200
        assert "text/event-stream" in msg_resp.headers["content-type"]

        # 3. Collect streamed events
        events = []
        async for line in msg_resp.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                events.append(json.loads(data_str))

        # 4. Build full response text
        full_response = ""
        for event in events:
            if "delta" in event:
                full_response += event["delta"]
            elif "thinking" in event:
                full_response += event["thinking"]

        # 5. Verify we got a non-empty response
        assert len(events) > 0, "Expected at least one streamed event"
        assert len(full_response.strip()) > 0, "Expected non-empty response text"

        print(f"\n✅ Live DuckDuckGo fallback response ({len(full_response)} chars):")
        print(f"   {full_response[:300]}...")

    finally:
        settings.enable_web_search = original_search
        settings.tavily_api_key = original_tavily_key


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_tavily_search_end_to_end(authenticated_client):
    """
    Live integration test using the REAL Tavily API key from .env.
    Verifies that Tavily works as the primary search engine without falling
    back to DuckDuckGo.

    Requires:
      - Ollama running locally with a model that supports tool calling
      - A valid TAVILY_API_KEY in .env
      - Run with: pytest -m live
    """
    from app.config import settings

    # Skip if no Tavily API key is configured
    if not settings.tavily_api_key:
        pytest.skip("TAVILY_API_KEY not configured in .env — skipping Tavily live test")

    original_search = settings.enable_web_search
    settings.enable_web_search = True

    try:
        # 1. Create a chat session
        session_resp = await authenticated_client.post(
            "/api/v1/chat/sessions",
            json={"title": "Tavily Search Test"}
        )
        assert session_resp.status_code == status.HTTP_201_CREATED
        session_id = session_resp.json()["id"]

        # 2. Send a real-time query
        msg_resp = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "Who won the latest Champions League final?",
                "use_rag": False,
                "web_search": True
            },
            timeout=120.0
        )
        assert msg_resp.status_code == 200
        assert "text/event-stream" in msg_resp.headers["content-type"]

        # 3. Collect streamed events
        events = []
        async for line in msg_resp.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                events.append(json.loads(data_str))

        # 4. Build full response text
        full_response = ""
        for event in events:
            if "delta" in event:
                full_response += event["delta"]
            elif "thinking" in event:
                full_response += event["thinking"]

        # 5. Verify we got a non-empty response
        assert len(events) > 0, "Expected at least one streamed event"
        assert len(full_response.strip()) > 0, "Expected non-empty response text"

        print(f"\n✅ Live TAVILY search response ({len(full_response)} chars):")
        print(f"   {full_response[:300]}...")

    finally:
        settings.enable_web_search = original_search
