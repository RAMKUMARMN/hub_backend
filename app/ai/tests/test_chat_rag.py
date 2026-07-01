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
from qdrant_client.models import Distance, TokenizerType, TextIndexParams, VectorParams, PayloadSchemaType

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

    await client.create_payload_index(
        collection_name=test_collection_name,
        field_name="filename",
        field_schema=TextIndexParams(
            type="text",
            tokenizer=TokenizerType.MULTILINGUAL,
            lowercase=True
        )
    )

    await client.create_payload_index(
        collection_name=test_collection_name,
        field_name="user_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    await client.create_payload_index(
        collection_name=test_collection_name,
        field_name="document_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    await client.create_payload_index(
        collection_name=test_collection_name,
        field_name="session_id",
        field_schema=PayloadSchemaType.KEYWORD,
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
@patch("app.ai.services.llm_service.httpx.AsyncClient.stream")
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
@patch("app.ai.local_client.LocalAIClient.extract_text")
@patch("app.ai.local_client.LocalAIClient.store_document_vectors")
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

@pytest.mark.live
@pytest.mark.asyncio
@patch("app.ai.local_client.LocalAIClient.extract_text")
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


@pytest.mark.live
@pytest.mark.asyncio
@patch("app.ai.local_client.LocalAIClient.extract_text")
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
@patch("app.ai.services.llm_service.httpx.AsyncClient.stream")
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


@pytest.mark.live
@pytest.mark.asyncio
async def test_search_relevant_chunks_prioritization(setup_qdrant_test_collection):
    """
    Verifies that search_relevant_chunks prioritizes documents belonging to
    the current session over global documents when scores are equal.
    """
    from app.ai import store_document_vectors, search_relevant_chunks
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    
    global_doc_id = uuid.uuid4()
    await store_document_vectors(
        user_id=user_id,
        document_id=global_doc_id,
        text="The quick brown fox jumps over the lazy dog.",
        filename="global.txt",
        session_id=None,
    )
    
    session_doc_id = uuid.uuid4()
    await store_document_vectors(
        user_id=user_id,
        document_id=session_doc_id,
        text="The quick brown fox jumps over the lazy dog.",
        filename="session.txt",
        session_id=session_id,
    )
    
    results = await search_relevant_chunks(
        user_id=user_id,
        query="brown fox",
        limit=2,
        allowed_document_ids=[global_doc_id, session_doc_id],
        session_id=session_id,
    )
    
    assert len(results) == 2
    assert results[0]["filename"] == "session.txt"
    assert results[1]["filename"] == "global.txt"



@pytest.mark.live
@pytest.mark.asyncio
@patch("app.ai.local_client.LocalAIClient.extract_text")
async def test_api_rag_prioritization(
    mock_extract,
    authenticated_client,
    setup_qdrant_test_collection,
):
    """
    Verifies that the chat messages endpoint prioritizes session-scoped document chunks
    over global document chunks through the HTTP API.
    """
    mock_extract.return_value = "The quick brown fox jumps over the lazy dog."

    session_resp = await authenticated_client.post("/api/v1/chat/sessions", json={"title": "Priority Session"})
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = session_resp.json()["id"]

    global_upload = await authenticated_client.post(
        "/api/v1/documents/upload",
        files={"file": ("global_priority.txt", b"dummy", "text/plain")}
    )
    assert global_upload.status_code == status.HTTP_202_ACCEPTED
    global_doc_id = global_upload.json()["id"]

    session_upload = await authenticated_client.post(
        f"/api/v1/documents/upload?session_id={session_id}",
        files={"file": ("session_priority.txt", b"dummy", "text/plain")}
    )
    assert session_upload.status_code == status.HTTP_202_ACCEPTED
    session_doc_id = session_upload.json()["id"]

    # Wait for the background worker to index both files in Qdrant
    processed = False
    for _ in range(40):
        await asyncio.sleep(0.5)
        list_resp = await authenticated_client.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        target_docs = [d for d in docs if d["id"] in [global_doc_id, session_doc_id]]
        if len(target_docs) == 2 and all(d["processed"] for d in target_docs):
            processed = True
            break
            
    assert processed, "Documents were not processed in time."

    msg_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "brown fox", "use_rag": True},
        timeout=50.0
    )
    assert msg_resp.status_code == 200

    # Parse sources payload from the stream
    sources = []
    async for line in msg_resp.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            payload = json.loads(data_str)
            if "sources" in payload:
                sources = payload["sources"]
                break

    assert len(sources) >= 2
    # The session document must rank higher than the global one due to the +0.15 boost
    assert sources[0]["filename"] == "session_priority.txt"
    assert sources[1]["filename"] == "global_priority.txt"


@pytest.mark.live
@pytest.mark.asyncio
async def test_search_relevant_chunks_filename_prioritization(setup_qdrant_test_collection):
    """
    Verifies that search_relevant_chunks prioritizes documents whose filename contains
    keywords from the query, using the +0.20 boost.
    """
    from app.ai import store_document_vectors, search_relevant_chunks
    user_id = uuid.uuid4()
    
    random_doc_id = uuid.uuid4()
    await store_document_vectors(
        user_id=user_id,
        document_id=random_doc_id,
        text="The quick brown fox jumps over the lazy dog.",
        filename="random_notes.txt",
        session_id=None,
    )
    
    resume_doc_id = uuid.uuid4()
    await store_document_vectors(
        user_id=user_id,
        document_id=resume_doc_id,
        text="The quick brown fox jumps over the lazy dog.",
        filename="resume_johndoe.pdf",
        session_id=None,
    )
    
    results = await search_relevant_chunks(
        user_id=user_id,
        query="explain my resume",
        limit=2,
        allowed_document_ids=[random_doc_id, resume_doc_id],
        session_id=None,
    )
    
    assert len(results) == 2
    assert results[0]["filename"] == "resume_johndoe.pdf"
    assert results[1]["filename"] == "random_notes.txt"


@pytest.mark.asyncio
@patch("app.ai.services.llm_service.httpx.AsyncClient.stream")
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
        yield json.dumps({"message": {"content": "Response"}})
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


@pytest.mark.live
@pytest.mark.asyncio
async def test_search_relevant_chunks_selected_similarity_boost(setup_qdrant_test_collection):
    """
    Verifies that search_relevant_chunks applies the +0.40 score boost
    for selected documents matching query keywords in name or content.
    """
    from app.ai import store_document_vectors, search_relevant_chunks
    user_id = uuid.uuid4()
    
    # Create two documents. One will be selected, the other not.
    selected_doc_id = uuid.uuid4()
    other_doc_id = uuid.uuid4()
    
    # Store selected doc (has matching filename keyword)
    await store_document_vectors(
        user_id=user_id,
        document_id=selected_doc_id,
        text="This contains some general info.",
        filename="selected_invoice.pdf",
    )
    
    # Store other doc (also has matching filename keyword, but not selected)
    await store_document_vectors(
        user_id=user_id,
        document_id=other_doc_id,
        text="This contains some general info.",
        filename="other_invoice.pdf",
    )
    
    # 1. Test filename match boost (+0.40) on selected doc
    # Both are similar to the query "invoice info" by filename.
    # But only selected_doc_id is in selected_document_ids.
    # Therefore, selected_doc_id should get the 0.40 boost and rank first.
    results = await search_relevant_chunks(
        user_id=user_id,
        query="invoice info",
        limit=2,
        allowed_document_ids=[selected_doc_id, other_doc_id],
        selected_document_ids=[selected_doc_id],
    )
    
    assert len(results) == 2
    assert results[0]["filename"] == "selected_invoice.pdf"
    
    # 2. Test content match boost (+0.40) on selected doc
    # Let's create two docs where the filename does NOT match, but the text content matches query keyword "banana".
    selected_banana_doc_id = uuid.uuid4()
    other_banana_doc_id = uuid.uuid4()
    
    await store_document_vectors(
        user_id=user_id,
        document_id=selected_banana_doc_id,
        text="The quick yellow banana is sweet.",
        filename="first.txt",
    )
    
    await store_document_vectors(
        user_id=user_id,
        document_id=other_banana_doc_id,
        text="The quick yellow banana is sweet.",
        filename="second.txt",
    )
    
    results_banana = await search_relevant_chunks(
        user_id=user_id,
        query="banana fruit",
        limit=2,
        allowed_document_ids=[selected_banana_doc_id, other_banana_doc_id],
        selected_document_ids=[selected_banana_doc_id],
    )
    
    assert len(results_banana) == 2
    # The selected document should be first since it got +0.40 boost
    assert results_banana[0]["filename"] == "first.txt"


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

