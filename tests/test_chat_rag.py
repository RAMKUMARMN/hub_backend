import pytest
import pytest_asyncio
import uuid
import json
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, TokenizerType, TextIndexParams, VectorParams

from app.main import app
from app.database import AsyncSessionLocal
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

@pytest_asyncio.fixture
async def setup_qdrant_test_collection():
    """
    Configures a temporary test collection in Qdrant for the duration of the test.
    Automatically overrides settings.qdrant_collection and deletes the collection on teardown.
    """
    original_collection = settings.qdrant_collection
    test_collection_name = f"temp_test_collection_{uuid.uuid4().hex}"
    settings.qdrant_collection = test_collection_name

    client = AsyncQdrantClient(url=settings.qdrant_url)

    if await client.collection_exists(test_collection_name):
        await client.delete_collection(test_collection_name)

    await client.create_collection(
        collection_name=test_collection_name,
        vectors_config=VectorParams(
            size=768,  # nomic-embed-text dimensions
            distance=Distance.COSINE
        )
    )

    await client.create_payload_index(
        collection_name=test_collection_name,
        field_name="text",
        field_schema=TextIndexParams(
            type="text",
            tokenizer=TokenizerType.MULTILINGUAL,
            lowercase=True
        )
    )

    yield client

    try:
        await client.delete_collection(test_collection_name)
    except Exception:
        pass
    
    settings.qdrant_collection = original_collection

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
@patch("app.routers.chat.httpx.AsyncClient.stream")
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
            json.dumps({"message": {"content": "Hello! "}}),
            json.dumps({"message": {"content": "I am "}}),
            json.dumps({"message": {"content": "an AI."}}),
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
@patch("app.routers.documents.extract_text")
@patch("app.routers.documents.store_document_vectors")
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
@patch("app.routers.documents.extract_text")
async def test_real_document_upload_and_rag_chat(mock_extract, authenticated_client, setup_qdrant_test_collection):
    """
    Performs a live end-to-end integration test of the RAG pipeline.
    Tests document vector storage in Qdrant, document processing polling,
    vector semantic search, and streaming Ollama completions.
    
    The external text extraction service is mocked to bypass dependency on the AI port 8003.
    """
    mock_extract.return_value = "CixioHub is developed by Team Beta. The current version of the project is 1.4.0."

    fact_file_content = b"CixioHub is developed by Team Beta. The current version of the project is 1.4.0."
    upload_resp = await authenticated_client.post(
        "/api/v1/documents/upload",
        files={"file": ("rag_fact.txt", fact_file_content, "text/plain")}
    )
    assert upload_resp.status_code == status.HTTP_202_ACCEPTED
    doc_id = upload_resp.json()["id"]

    processed = False
    for _ in range(40):
        await asyncio.sleep(0.5)
        list_resp = await authenticated_client.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        target_doc = next((d for d in docs if d["id"] == doc_id), None)
        if target_doc and target_doc["processed"]:
            processed = True
            break
            
    assert processed, "Document was not processed in time."

    session_resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Real RAG Chat Test"}
    )
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = session_resp.json()["id"]

    msg_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "What is the current version of the CixioHub project?", "use_rag": True},
        timeout=60.0
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

    assert len(events) > 0
    
    assert "sources" in events[0]
    sources = events[0]["sources"]
    assert len(sources) > 0
    assert any(s["filename"] == "rag_fact.txt" for s in sources)

    full_response = ""
    for event in events[1:]:
        if "delta" in event:
            full_response += event["delta"]
        elif "thinking" in event:
            full_response += event["thinking"]

    assert "1.4" in full_response, f"Expected fact '1.4' not found in response: '{full_response}'"
    print(f"\n✅ Real RAG response: {full_response}")


@pytest.mark.asyncio
@patch("app.routers.documents.extract_text")
async def test_session_scoped_rag_isolation(
    mock_extract,
    authenticated_client,
    setup_qdrant_test_collection,
):
    """
    Tests isolation between global files and session-scoped files:
    1. Creates Session A and Session B.
    2. Uploads:
       - global_doc.txt (global, no session_id)
       - session_a_doc.txt (scoped to Session A)
       - session_b_doc.txt (scoped to Session B)
    3. Verifies that RAG in Session A retrieves chunks only from global_doc.txt and session_a_doc.txt.
    4. Verifies that RAG in Session B retrieves chunks only from global_doc.txt and session_b_doc.txt.
    """
    # Define text extraction mock outputs
    def mock_extract_side_effect(file_path, file_type):
        if "global" in file_path:
            return "This is global knowledge. The key code is GLOBAL_123."
        elif "session_a" in file_path:
            return "This is unique session A knowledge. The key code is ALPHABET_A."
        elif "session_b" in file_path:
            return "This is unique session B knowledge. The key code is ALPHABET_B."
        return "Generic fallback content."

    mock_extract.side_effect = mock_extract_side_effect

    # 1. Create Session A and Session B
    session_a_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Session A"})
    assert session_a_resp.status_code == status.HTTP_201_CREATED
    session_a_id = session_a_resp.json()["id"]

    session_b_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Session B"})
    assert session_b_resp.status_code == status.HTTP_201_CREATED
    session_b_id = session_b_resp.json()["id"]

    # 2. Upload the three documents
    # Global document (no session_id)
    global_upload = await authenticated_client.post(
        "/api/v1/documents/upload",
        files={"file": ("global_doc.txt", b"dummy content", "text/plain")}
    )
    assert global_upload.status_code == status.HTTP_202_ACCEPTED
    global_doc_id = global_upload.json()["id"]
    assert global_upload.json()["session_id"] is None

    # Session A document
    session_a_upload = await authenticated_client.post(
        f"/api/v1/documents/upload?session_id={session_a_id}",
        files={"file": ("session_a_doc.txt", b"dummy content", "text/plain")}
    )
    assert session_a_upload.status_code == status.HTTP_202_ACCEPTED
    session_a_doc_id = session_a_upload.json()["id"]
    assert session_a_upload.json()["session_id"] == session_a_id

    # Session B document
    session_b_upload = await authenticated_client.post(
        f"/api/v1/documents/upload?session_id={session_b_id}",
        files={"file": ("session_b_doc.txt", b"dummy content", "text/plain")}
    )
    assert session_b_upload.status_code == status.HTTP_202_ACCEPTED
    session_b_doc_id = session_b_upload.json()["id"]
    assert session_b_upload.json()["session_id"] == session_b_id

    # 3. Wait for all documents to be processed by background tasks
    processed = False
    for _ in range(40):
        await asyncio.sleep(0.5)
        list_resp = await authenticated_client.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        
        target_docs = [d for d in docs if d["id"] in [global_doc_id, session_a_doc_id, session_b_doc_id]]
        if len(target_docs) == 3 and all(d["processed"] for d in target_docs):
            processed = True
            break
            
    assert processed, "Not all documents were processed in time."

    # 4. Verify RAG in Session A (should match global_doc.txt and session_a_doc.txt, NOT session_b_doc.txt)
    msg_a_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_a_id}/messages",
        json={"content": "What is the key code?", "use_rag": True},
        timeout=50.0
    )
    assert msg_a_resp.status_code == 200

    # Parse sources from SSE stream
    sources_a = []
    async for line in msg_a_resp.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            payload = json.loads(data_str)
            if "sources" in payload:
                sources_a = payload["sources"]
                break

    assert len(sources_a) > 0
    filenames_a = [s["filename"] for s in sources_a]
    assert "global_doc.txt" in filenames_a or "session_a_doc.txt" in filenames_a
    assert "session_b_doc.txt" not in filenames_a

    # 5. Verify RAG in Session B (should match global_doc.txt and session_b_doc.txt, NOT session_a_doc.txt)
    msg_b_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_b_id}/messages",
        json={"content": "What is the key code?", "use_rag": True},
        timeout=50.0
    )
    assert msg_b_resp.status_code == 200

    sources_b = []
    async for line in msg_b_resp.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            payload = json.loads(data_str)
            if "sources" in payload:
                sources_b = payload["sources"]
                break

    assert len(sources_b) > 0
    filenames_b = [s["filename"] for s in sources_b]
    assert "global_doc.txt" in filenames_b or "session_b_doc.txt" in filenames_b
    assert "session_a_doc.txt" not in filenames_b


@pytest.mark.asyncio
@patch("app.routers.chat.httpx.AsyncClient.stream")
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
            json.dumps({"message": {"content": "Direct response content"}}),
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
