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
