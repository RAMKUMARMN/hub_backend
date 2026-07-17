import pytest
import pytest_asyncio
import uuid
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select, text

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.chat import ChatMessage, ChatSession
from app.auth.security.password import hash_password
from app.ai.api.chat import _summarize_and_prune
from app.ai.client import AIClient

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
async def test_pruning_marks_messages_as_summarized_and_keeps_in_db(authenticated_client):
    """
    Verifies that _summarize_and_prune:
    1. Sets is_summarized=True for all messages except the last 4 active ones.
    2. Does NOT delete messages from the database.
    3. Saves the summarized context in ChatSession.summary.
    """
    # Create session
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Test Pruning"}
    )
    session_id = uuid.UUID(resp.json()["id"])

    # Create 12 messages in DB manually with incremental timestamps
    base_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    async with AsyncSessionLocal() as db:
        for i in range(12):
            role = "user" if i % 2 == 0 else "assistant"
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=f"Message {i}",
                created_at=base_time + timedelta(seconds=i)
            )
            db.add(msg)
        await db.commit()

    # Create a mock AI client
    mock_ai = AsyncMock(spec=AIClient)
    mock_ai.summarize_text.return_value = "Merged conversation summary."

    # Run _summarize_and_prune
    await _summarize_and_prune(session_id, mock_ai)

    # Verify database state
    async with AsyncSessionLocal() as db:
        # 1. Verify summary was saved
        sess_result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = sess_result.scalar_one()
        assert session.summary == "Merged conversation summary."

        # 2. Verify all 12 messages still exist in the database (non-destructive!)
        msgs_result = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        all_msgs = msgs_result.scalars().all()
        assert len(all_msgs) == 12

        # 3. Verify exactly 8 messages are marked is_summarized=True
        # (since 12 total, and we keep the last 4: indices 8, 9, 10, 11)
        summarized_msgs = [m for m in all_msgs if m.is_summarized]
        active_msgs = [m for m in all_msgs if not m.is_summarized]
        assert len(summarized_msgs) == 8
        assert len(active_msgs) == 4

        # Verify active ones are the last 4
        for m in active_msgs:
            assert "Message 8" in m.content or "Message 9" in m.content or "Message 10" in m.content or "Message 11" in m.content


@pytest.mark.asyncio
@patch("app.ai.remote_client.httpx.AsyncClient.stream")
async def test_send_message_uses_only_unsummarized_history(mock_stream_post, authenticated_client):
    """
    Verifies that send_message:
    1. Retrieves only non-summarized messages for active context.
    2. Injects any existing summary into the system instruction.
    """
    # Create session
    resp = await authenticated_client.post(
        "/api/v1/chat/sessions",
        json={"title": "Test Chat History Filter"}
    )
    session_id = uuid.UUID(resp.json()["id"])

    # Insert 12 messages in DB, first 8 marked is_summarized=True, with manual incremental timestamps
    base_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    async with AsyncSessionLocal() as db:
        # Update session summary first so it's populated
        sess_result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = sess_result.scalar_one()
        session.summary = "Pruned summary context"

        for i in range(12):
            role = "user" if i % 2 == 0 else "assistant"
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=f"Message {i}",
                is_summarized=(i < 8), # Mark first 8 as summarized
                created_at=base_time + timedelta(seconds=i)
            )
            db.add(msg)
        await db.commit()

    # Mock Ollama streaming chunks
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    async def mock_aiter_lines():
        yield 'data: ' + json.dumps({"delta": "Response to new message"})
        yield 'data: [DONE]'
    mock_response.aiter_lines = mock_aiter_lines

    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    mock_stream_post.return_value = AsyncContextManagerMock()

    # Call endpoint to send the 13th message
    msg_resp = await authenticated_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "New query", "use_rag": False}
    )
    assert msg_resp.status_code == 200

    # Verify the messages sent to the LLM (ollama_messages list)
    called_args, called_kwargs = mock_stream_post.call_args
    payload = called_kwargs["json"]
    messages = payload["messages"]

    # Assert system prompt has the summary context
    assert messages[0]["role"] == "system"
    assert "Pruned summary context" in messages[0]["content"]

    # Assert history has ONLY the active messages (indices 8, 9, 10, 11) + the new user query
    # So total history messages should be 6: 1 system prompt + 4 history + 1 new query
    assert len(messages) == 6
    
    # Check roles and content of active history in the prompt
    for idx, msg in enumerate(messages[1:-1]):
        original_index = 8 + idx
        role = "user" if original_index % 2 == 0 else "assistant"
        assert msg["role"] == role
        assert msg["content"] == f"Message {original_index}"
    
    # Check final new user message
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "New query"
