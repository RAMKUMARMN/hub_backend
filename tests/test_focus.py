import pytest
import pytest_asyncio
import uuid
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.focus import FocusSession
from app.auth.security.password import hash_password
from app.config import settings

TEST_EMAIL = settings.test_email
TEST_PASSWORD = settings.test_password
TEST_NAME = settings.test_name

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    from app.database import engine
    await engine.dispose()
    from app.redis import redis_client
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users, focus_sessions, achievements, user_achievements CASCADE;"))
        await session.commit()
    yield

@pytest_asyncio.fixture
async def seed_user():
    async with AsyncSessionLocal() as session:
        user = User(
            email=TEST_EMAIL,
            full_name=TEST_NAME,
            hashed_password=hash_password(TEST_PASSWORD),
            is_active=True,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

@pytest_asyncio.fixture
async def auth_headers(client, seed_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}

@pytest.mark.asyncio
async def test_start_focus_session_success(client, auth_headers):
    response = await client.post(
        "/api/v1/focus/sessions",
        json={"type": "focus"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["type"] == "focus"
    assert data["status"] == "started"

@pytest.mark.asyncio
async def test_start_focus_session_invalid_type(client, auth_headers):
    response = await client.post(
        "/api/v1/focus/sessions",
        json={"type": "invalid_type"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_start_focus_session_already_active(client, auth_headers):
    # Start first session
    response1 = await client.post(
        "/api/v1/focus/sessions",
        json={"type": "focus"},
        headers=auth_headers
    )
    assert response1.status_code == status.HTTP_201_CREATED

    # Attempt second session
    response2 = await client.post(
        "/api/v1/focus/sessions",
        json={"type": "short_break"},
        headers=auth_headers
    )
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert response2.json()["detail"] == "User already has an active focus session"

@pytest.mark.asyncio
async def test_pause_resume_stop_focus_session(client, auth_headers):
    # Start session
    response = await client.post(
        "/api/v1/focus/sessions",
        json={"type": "focus"},
        headers=auth_headers
    )
    session_id = response.json()["id"]

    # Pause session
    pause_response = await client.post(
        f"/api/v1/focus/sessions/{session_id}/pause",
        headers=auth_headers
    )
    assert pause_response.status_code == status.HTTP_200_OK
    assert pause_response.json()["status"] == "paused"

    # Resume session
    resume_response = await client.post(
        f"/api/v1/focus/sessions/{session_id}/resume",
        headers=auth_headers
    )
    assert resume_response.status_code == status.HTTP_200_OK
    assert resume_response.json()["status"] == "started"

    # Stop session
    stop_response = await client.post(
        f"/api/v1/focus/sessions/{session_id}/stop",
        params={"status": "completed"},
        headers=auth_headers
    )
    assert stop_response.status_code == status.HTTP_200_OK
    assert stop_response.json()["status"] == "completed"
    assert stop_response.json()["duration_minutes"] is not None

@pytest.mark.asyncio
async def test_get_metrics(client, auth_headers, seed_user):
    # Seed a completed focus session
    async with AsyncSessionLocal() as db_session:
        focus_sess = FocusSession(
            user_id=seed_user.id,
            type="focus",
            status="completed",
            duration_minutes=25
        )
        db_session.add(focus_sess)
        await db_session.commit()

    # Get metrics
    response = await client.get("/api/v1/focus/metrics", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_focus_minutes"] == 25
    assert data["total_break_minutes"] == 0
    assert data["productivity_score"] == 100
