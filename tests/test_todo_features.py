import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.todo import Todo
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
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users, todos CASCADE;"))
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
async def test_create_todo_default_priority(client, auth_headers):
    response = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={"title": "Default Priority Task"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Default Priority Task"
    assert data["priority"] == "medium"
    assert data["reminder_time"] is None

@pytest.mark.asyncio
async def test_create_todo_explicit_priority(client, auth_headers):
    # Test High Priority
    response_high = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={"title": "High Priority Task", "priority": "high"}
    )
    assert response_high.status_code == status.HTTP_201_CREATED
    assert response_high.json()["priority"] == "high"

    # Test Low Priority
    response_low = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={"title": "Low Priority Task", "priority": "low"}
    )
    assert response_low.status_code == status.HTTP_201_CREATED
    assert response_low.json()["priority"] == "low"

@pytest.mark.asyncio
async def test_create_todo_invalid_priority_fails(client, auth_headers):
    response = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={"title": "Invalid Priority Task", "priority": "urgent"}
    )
    # Pydantic validation error should trigger status 422
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_create_todo_with_reminder(client, auth_headers):
    reminder_time = datetime.now(timezone.utc) + timedelta(hours=3)
    response = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={
            "title": "Task with Reminder",
            "reminder_time": reminder_time.isoformat()
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["reminder_time"] is not None

@pytest.mark.asyncio
async def test_update_todo_priority_and_reminder(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/todos/",
        headers=auth_headers,
        json={"title": "Mutable Task"}
    )
    todo_id = create_resp.json()["id"]

    reminder_time = datetime.now(timezone.utc) + timedelta(hours=5)
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        headers=auth_headers,
        json={
            "priority": "high",
            "reminder_time": reminder_time.isoformat()
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["priority"] == "high"
    assert data["reminder_time"] is not None
