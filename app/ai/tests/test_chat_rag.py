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
from app.models.document import Document
from app.models.user import User
from app.auth.security.password import hash_password
from app.config import settings

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    """Wipes test database tables before each test case to guarantee isolated state."""
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
    """Seeds a test user and returns an authenticated HTTP client."""
    async with AsyncSessionLocal() as session:
        user = User(
            email="test_rag@tkmce.ac.in",
            full_name="RAG Tester",
            hashed_password=hash_password("securepassword123"),
            is_active=True,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test_rag@tkmce.ac.in", "password": "securepassword123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

# ── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_sessions(authenticated_client):
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Test Session"}
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["title"] == "Test Session"
    session_id = data["id"]

    list_resp = await authenticated_client.get("/api/v1/chat/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id

@pytest.mark.asyncio
@patch("app.ai.remote_client.httpx.AsyncClient.stream")
async def test_send_message_stream(mock_stream_post, authenticated_client):
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Chat Stream Test"}
    )
    session_id = resp.json()["id"]

    # Mocking Ollama streaming chunks
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        lines = [
            'data: ' + json.dumps({"delta": "Hello! "}),
            'data: ' + json.dumps({"delta": "I am "}),
            'data: ' + json.dumps({"delta": "an AI."}),
            'data: [DONE]',
        ]
        for line in lines:
            yield line

    mock_response.aiter_lines = mock_aiter_lines
    
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_stream_post.return_value = AsyncContextManagerMock()

    msg_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Who are you?", "use_rag": False}
    )
    assert msg_resp.status_code == 200
    assert "text/event-stream" in msg_resp.headers["content-type"]

    events = []
    async for line in msg_resp.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            events.append(json.loads(data_str))

    assert len(events) == 3
    assert events[0]["delta"] == "Hello! "
    assert events[1]["delta"] == "I am "
    assert events[2]["delta"] == "an AI."

@pytest.mark.asyncio
@patch("app.routers.documents.save_file")
@patch("app.ai.remote_client.RemoteAIClient.extract_text")
@patch("app.ai.remote_client.RemoteAIClient.store_document_vectors")
async def test_upload_document(mock_store, mock_extract, mock_save, authenticated_client):
    mock_save.return_value = "documents/test_user/test.txt"
    mock_extract.return_value = "This is a test document content for RAG."
    mock_store.return_value = 1

    file_content = b"This is a test document content for RAG."
    resp = await authenticated_client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", file_content, "text/plain")}
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["processed"] is False



@pytest.mark.asyncio
@patch("app.ai.remote_client.httpx.AsyncClient.stream")
async def test_thinking_mode_toggle(mock_stream_post, authenticated_client):
    """
    Verifies that the thinking_mode query parameter is accepted by the schema
    and successfully streams a response using a mock LLM (takes <0.1s to complete).
    """
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Thinking Mode Toggle Test"}
    )
    session_id = resp.json()["id"]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        lines = [
            'data: ' + json.dumps({"delta": "Direct response content"}),
            'data: [DONE]',
        ]
        for line in lines:
            yield line

    mock_response.aiter_lines = mock_aiter_lines
    
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_stream_post.return_value = AsyncContextManagerMock()

    # Test with thinking_mode=False
    msg_resp_false = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Direct query", "use_rag": False, "thinking_mode": False}
    )
    assert msg_resp_false.status_code == 200

    # Test with thinking_mode=True
    msg_resp_true = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Reasoning query", "use_rag": False, "thinking_mode": True}
    )
    assert msg_resp_true.status_code == 200







@pytest.mark.asyncio
@patch("app.ai.remote_client.httpx.AsyncClient.stream")
async def test_chat_rag_chunk_limit_and_get_stream(mock_stream_post, authenticated_client):
    """
    Verifies that the SendMessageRequest schema validates rag_chunk_limit bounds,
    the POST endpoint passes rag_chunk_limit correctly, and the GET stream
    endpoint resolves tokens correctly and supports streaming.
    """
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Test Session"}
    )
    session_id = resp.json()["id"]

    # Mock Ollama streaming
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    async def mock_aiter_lines():
        yield 'data: ' + json.dumps({"delta": "Response"})
        yield 'data: [DONE]'
    mock_response.aiter_lines = mock_aiter_lines
    
    class AsyncContextManagerMock:
        async def __aenter__(self): return mock_response
        async def __aexit__(self, et, ev, tb): pass

    mock_stream_post.return_value = AsyncContextManagerMock()

    # 1. Test POST validation fails for range limits (e.g., < 4 or > 64)
    resp_invalid_low = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "query", "use_rag": True, "rag_chunk_limit": 3}
    )
    assert resp_invalid_low.status_code == 422

    resp_invalid_high = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "query", "use_rag": True, "rag_chunk_limit": 65}
    )
    assert resp_invalid_high.status_code == 422

    resp_invalid_mode = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "query", "use_rag": True, "retrieval_mode": "fuzzy"}
    )
    assert resp_invalid_mode.status_code == 422

    # 2. Test POST works with valid rag_chunk_limit (e.g. 16)
    resp_valid = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={
            "content": "query",
            "use_rag": False,
            "retrieval_mode": "hybrid",
            "rag_chunk_limit": 16,
        }
    )
    assert resp_valid.status_code == 200

    # 3. Test GET message stream endpoint
    # Extract JWT token from the client headers
    auth_header = authenticated_client.headers.get("Authorization")
    token = auth_header.split(" ")[1] if auth_header else ""

    get_resp = await authenticated_client.get(
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        params={
            "content": "GET query",
            "token": token,
            "use_rag": False,
            "thinking_mode": True,
            "retrieval_mode": "keyword",
            "rag_chunk_limit": 8
        }
    )
    assert get_resp.status_code == 200
    assert "text/event-stream" in get_resp.headers["content-type"]


@pytest.mark.asyncio
async def test_chat_rag_passes_hybrid_retrieval_mode(authenticated_client):
    """
    Verifies the chat API passes retrieval_mode='hybrid' into the AI RAG client
    when RAG is enabled.
    """
    session_resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Hybrid Retrieval Test"},
    )
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            text("SELECT id FROM users WHERE email = 'test_rag@tkmce.ac.in'")
        )
        user_id = uuid.UUID(str(user_result.scalar_one()))

        doc = Document(
            user_id=user_id,
            session_id=None,
            filename="coa_notes.txt",
            file_type="txt",
            file_size=128,
            storage_path="documents/test/coa_notes.txt",
            processed=True,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        document_id = doc.id

    class FakeAIClient:
        def __init__(self):
            self.search_relevant_chunks = AsyncMock(
                return_value=[
                    {
                        "text": "Module 4 covers instruction pipelining.",
                        "filename": "coa_notes.txt",
                        "document_id": str(document_id),
                        "score": 0.91,
                        "match_type": "hybrid",
                    }
                ]
            )

        async def chat_stream(self, messages, think=True):
            yield "Hybrid answer"

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    try:
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "Explain module 4 pipelining from COA notes",
                "use_rag": True,
                "use_hyde": True,
                "retrieval_mode": "hybrid",
                "rag_chunk_limit": 4,
            },
        )
        assert response.status_code == 200

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                events.append(json.loads(data_str))

        assert events[0]["sources"][0]["match_type"] == "hybrid"
        fake_ai.search_relevant_chunks.assert_awaited_once()
        call_kwargs = fake_ai.search_relevant_chunks.await_args.kwargs
        assert call_kwargs["retrieval_mode"] == "hybrid"
        assert call_kwargs["use_hyde"] is True
        assert document_id in call_kwargs["allowed_document_ids"]
    finally:
        app.dependency_overrides.pop(get_ai_client, None)


@pytest.mark.asyncio
async def test_chat_get_stream_passes_hyde_toggle(authenticated_client):
    """
    Verifies the EventSource-compatible GET stream endpoint parses use_hyde and
    passes it into the RAG client.
    """
    session_resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "GET HyDE Test"},
    )
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            text("SELECT id FROM users WHERE email = 'test_rag@tkmce.ac.in'")
        )
        user_id = uuid.UUID(str(user_result.scalar_one()))

        doc = Document(
            user_id=user_id,
            session_id=None,
            filename="hyde_notes.txt",
            file_type="txt",
            file_size=128,
            storage_path="documents/test/hyde_notes.txt",
            processed=True,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

    class FakeAIClient:
        def __init__(self):
            self.search_relevant_chunks = AsyncMock(
                return_value=[
                    {
                        "text": "HyDE retrieves by embedding a hypothetical answer.",
                        "filename": "hyde_notes.txt",
                        "document_id": str(doc.id),
                        "score": 0.9,
                        "match_type": "semantic",
                    }
                ]
            )

        async def chat_stream(self, messages, think=True):
            yield "GET HyDE answer"

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    try:
        auth_header = authenticated_client.headers.get("Authorization")
        token = auth_header.split(" ")[1] if auth_header else ""
        response = await authenticated_client.get(
            f"/api/v1/chat/sessions/{session_id}/messages/stream",
            params={
                "content": "Explain HyDE",
                "token": token,
                "use_rag": True,
                "use_hyde": True,
                "retrieval_mode": "semantic",
            },
        )
        assert response.status_code == 200

        async for _line in response.aiter_lines():
            pass

        call_kwargs = fake_ai.search_relevant_chunks.await_args.kwargs
        assert call_kwargs["use_hyde"] is True
    finally:
        app.dependency_overrides.pop(get_ai_client, None)



@pytest.mark.asyncio
async def test_automatic_session_image_recall(authenticated_client):
    """
    Verifies that the chat router automatically detects a generic visual query
    (e.g., 'explain this image') and force-queries Qdrant for the latest session image.
    """
    # 1. Create a session
    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Session Recall"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    # 2. Setup user and document row in PostgreSQL
    async with AsyncSessionLocal() as db:
        user_res = await db.execute(text("SELECT id FROM users WHERE email = 'test_rag@tkmce.ac.in'"))
        user_id = uuid.UUID(str(user_res.scalar_one()))

        doc = Document(
            user_id=user_id,
            session_id=session_id,
            filename="diagram.png",
            file_type="png",
            file_size=128,
            storage_path="documents/test/diagram.png",
            processed=True,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        image_doc_id = doc.id

    # 3. Create a fake AI client that returns a mock search result
    class FakeAIClient:
        def __init__(self):
            self.search_relevant_chunks = AsyncMock(side_effect=self._mock_search)

        def _mock_search(self, *args, **kwargs):
            # If the search specifically targets our image_doc_id (because of Method 2 bypass)
            allowed_docs = kwargs.get("allowed_document_ids")
            if allowed_docs == [image_doc_id]:
                return [
                    {
                        "text": "[Image Description - Page 1]: This is a blue circle.",
                        "filename": "diagram.png",
                        "document_id": str(image_doc_id),
                        "score": 1.0,
                        "match_type": "semantic"
                    }
                ]
            # Standard search returns empty/unrelated
            return []

        async def chat_stream(self, messages, think=True):
            yield "Response"

        async def chat_with_tools(self, messages, tools=None, think=True):
            return {"role": "assistant", "content": "Response"}

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    try:
        # Call the chat endpoint with RAG enabled, asking a generic visual query
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "explain this image",
                "use_rag": True,
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

        # Check that diagram.png was injected as a source even though standard search would return empty
        assert len(events) > 0
        sources = events[0].get("sources", [])
        assert len(sources) > 0
        assert sources[0]["filename"] == "diagram.png"
        assert "blue circle" in sources[0]["text"]

        # Verify that search_relevant_chunks was called with allowed_document_ids set specifically to our image_doc_id
        fake_ai.search_relevant_chunks.assert_any_call(
            user_id=user_id,
            query="explain this image",
            limit=4,
            retrieval_mode="semantic",
            use_hyde=False,
            allowed_document_ids=[image_doc_id],
            session_id=session_id,
            selected_document_ids=[image_doc_id],
            use_reranker=False,
        )
    finally:
        app.dependency_overrides.pop(get_ai_client, None)


@pytest.mark.asyncio
async def test_agentic_reinspection_fallback(authenticated_client):
    """
    Verifies that Option A (Agentic Fallback) triggers a tool call when a visual context chunk is retrieved,
    runs reinspect_page, feeds the results back to the LLM, and streams the final answer.
    """
    # 1. Create a session
    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Agentic Fallback"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    # 2. Setup user and document row in PostgreSQL
    async with AsyncSessionLocal() as db:
        user_res = await db.execute(text("SELECT id FROM users WHERE email = 'test_rag@tkmce.ac.in'"))
        user_id = uuid.UUID(str(user_res.scalar_one()))

        doc = Document(
            user_id=user_id,
            session_id=session_id,
            filename="report.pdf",
            file_type="pdf",
            file_size=2048,
            storage_path="documents/test/report.pdf",
            processed=True,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    # 3. Create a fake AI client
    class FakeAIClient:
        def __init__(self):
            self.search_relevant_chunks = AsyncMock(return_value=[
                {
                    "text": f"[Image Description - Page 3]: A bar chart showing crop yield over the years.",
                    "filename": "report.pdf",
                    "document_id": str(doc_id),
                    "score": 0.95,
                    "match_type": "semantic"
                }
            ])
            self.calls = 0

        async def chat_with_tools(self, messages, tools=None, think=True):
            self.calls += 1
            if self.calls == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fallback_123",
                            "type": "function",
                            "function": {
                                "name": "reinspect_document_page",
                                "arguments": {
                                    "document_id": str(doc_id),
                                    "page_number": 3,
                                    "specific_question": "What is the yield value for 2021?"
                                }
                            }
                        }
                    ]
                }
            else:
                has_tool_msg = any(msg.get("role") == "tool" and "15 tons per acre" in msg.get("content") for msg in messages)
                if has_tool_msg:
                    content = "In 2021, the crop yield was 15 tons per acre."
                else:
                    content = "Standard response without tool context."
                return {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": None
                }

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    # Mock the reinspect_page call in vision_service
    with patch("app.ai.services.vision_service.reinspect_page", new_callable=AsyncMock) as mock_reinspect:
        mock_reinspect.return_value = "Crop yield for 2021: 15 tons per acre."

        try:
            # Call the chat endpoint with RAG enabled
            response = await authenticated_client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={
                    "content": "What was the crop yield in 2021 on page 3?",
                    "use_rag": True,
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

            # Verify response content
            assert len(events) > 0
            # First event is source citations
            assert "sources" in events[0]
            
            # Find the delta/response event
            full_text = "".join(ev.get("delta", "") for ev in events if "delta" in ev)
            assert "15 tons per acre" in full_text

            # Assertions on tool invocation
            assert fake_ai.calls == 2
            mock_reinspect.assert_called_once_with(
                pdf_path="uploads/documents/test/report.pdf",
                page_number=3,
                specific_question="What is the yield value for 2021?"
            )

        finally:
            app.dependency_overrides.pop(get_ai_client, None)


@pytest.mark.asyncio
async def test_non_rag_document_context_injection(authenticated_client):
    # 1. Create session
    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Non-RAG Session"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    # 2. Insert a document belonging to the active session and mark as processed
    async with AsyncSessionLocal() as db_session:
        from sqlalchemy import select
        from app.models.document import Document
        from app.models.user import User
        user_result = await db_session.execute(select(User).limit(1))
        user = user_result.scalar_one()

        doc = Document(
            user_id=user.id,
            session_id=session_id,
            filename="lecture_notes.txt",
            file_type="txt",
            file_size=100,
            storage_path="documents/lecture_notes.txt",
            version=1,
            processed=True,
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)
        doc_id = doc.id

    # 3. Setup Fake AI Client to capture arguments
    captured_messages = []
    class FakeAIClient:
        async def extract_text(self, path, file_type):
            return "This is the full text of the lecture notes document."

        async def chat_stream(self, messages, think=True):
            nonlocal captured_messages
            captured_messages = messages
            yield "Response to lecture notes query."

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    try:
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "Summarize my lecture notes.",
                "use_rag": False,
                "document_ids": [str(doc_id)],
            },
        )
        assert response.status_code == 200

        # Read the event stream
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                events.append(json.loads(data_str))

        assert len(events) > 0
        assert "".join(e.get("delta", "") for e in events) == "Response to lecture notes query."

        # Verify the captured prompt contains the extracted document text
        system_instruction_msg = [m for m in captured_messages if m["role"] == "system"]
        assert len(system_instruction_msg) > 0
        system_content = system_instruction_msg[0]["content"]
        assert "This is the full text of the lecture notes document." in system_content
        assert "--- DOCUMENT CONTEXT ---" in system_content

    finally:
        app.dependency_overrides.pop(get_ai_client, None)


@pytest.mark.asyncio
async def test_agent_mode_tool_routing(authenticated_client):
    # 1. Create session
    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Agent Session"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = uuid.UUID(session_resp.json()["id"])

    # 2. Setup Fake AI Client to trigger a tool call first, then return text on second turn
    captured_messages = []
    turns = 0

    class FakeAIClient:
        async def chat_with_tools(self, messages, tools, think=True):
            nonlocal captured_messages, turns
            captured_messages = messages
            turns += 1
            if turns == 1:
                # Return a mock tool call requesting list_session_documents
                return {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_list_docs",
                            "type": "function",
                            "function": {
                                "name": "list_session_documents",
                                "arguments": "{}"
                            }
                        }
                    ]
                }
            else:
                # Return standard assistant text response
                return {
                    "role": "assistant",
                    "content": "I see you have no documents in this session."
                }

        async def chat_stream(self, messages, think=True):
            yield "Streamed response."

    fake_ai = FakeAIClient()
    app.dependency_overrides[get_ai_client] = lambda: fake_ai

    try:
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "List my documents please.",
                "agent_mode": True
            },
        )
        assert response.status_code == 200

        # Read the event stream
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                events.append(json.loads(data_str))

        assert len(events) > 0
        # The first event in tool loop streams intermediate thinking or tool actions
        # Turn 2 should stream the final answer
        # Verify the captured messages contains the tool response message!
        tool_msgs = [m for m in captured_messages if m["role"] == "tool"]
        assert len(tool_msgs) > 0
        assert tool_msgs[0]["tool_call_id"] == "call_list_docs"
        assert "No documents have been uploaded" in tool_msgs[0]["content"]

    finally:
        app.dependency_overrides.pop(get_ai_client, None)

