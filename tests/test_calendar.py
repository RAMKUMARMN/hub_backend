import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.todo import Todo
from app.models.calendar import CalendarEvent
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
    from app.redis import redis_client
    await engine.dispose()
    try:
        await redis_client.aclose()
    except Exception:
        pass
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users, todos, calendar_events CASCADE;"))
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
async def seed_other_user():
    async with AsyncSessionLocal() as session:
        user = User(
            email="other@example.com",
            full_name="Other User",
            hashed_password=hash_password("otherpassword"),
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

@pytest_asyncio.fixture
async def seed_todo(seed_user):
    async with AsyncSessionLocal() as session:
        todo = Todo(
            user_id=seed_user.id,
            title="Calendar-linked Task",
            description="Testing task linkage",
            completed=False
        )
        session.add(todo)
        await session.commit()
        await session.refresh(todo)
        return todo

@pytest.mark.asyncio
async def test_create_calendar_event_success(client, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    reminder = start - timedelta(minutes=15)

    response = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={
            "title": "Study Session",
            "description": "Prepare for exams",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "is_recurring": True,
            "recurrence_rule": "FREQ=DAILY",
            "reminder_time": reminder.isoformat()
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Study Session"
    assert data["description"] == "Prepare for exams"
    assert data["is_recurring"] is True
    assert data["recurrence_rule"] == "FREQ=DAILY"
    assert "id" in data

@pytest.mark.asyncio
async def test_create_calendar_event_with_todo(client, auth_headers, seed_todo):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    response = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={
            "title": "Event Linked to Task",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "todo_id": str(seed_todo.id)
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["todo_id"] == str(seed_todo.id)

@pytest.mark.asyncio
async def test_create_calendar_event_invalid_todo(client, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    response = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={
            "title": "Invalid Event Link",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "todo_id": str(uuid.uuid4())
        }
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Associated todo item not found or not owned by user"

@pytest.mark.asyncio
async def test_list_calendar_events(client, auth_headers):
    start1 = datetime.now(timezone.utc) + timedelta(hours=1)
    end1 = start1 + timedelta(hours=1)
    start2 = start1 + timedelta(days=2)
    end2 = start2 + timedelta(hours=1)

    # Create two events
    await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={"title": "Event 1", "start_time": start1.isoformat(), "end_time": end1.isoformat()}
    )
    await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={"title": "Event 2", "start_time": start2.isoformat(), "end_time": end2.isoformat()}
    )

    # List all
    response = await client.get("/api/v1/calendar/events", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2

    # Filter with start/end to fetch only Event 1
    cutoff = start1 + timedelta(days=1)
    filtered_response = await client.get(
        "/api/v1/calendar/events",
        params={"end": cutoff.isoformat()},
        headers=auth_headers
    )
    assert filtered_response.status_code == status.HTTP_200_OK
    data = filtered_response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Event 1"

@pytest.mark.asyncio
async def test_get_calendar_event(client, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    create_resp = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={"title": "Target Event", "start_time": start.isoformat(), "end_time": end.isoformat()}
    )
    event_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/calendar/events/{event_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Target Event"

@pytest.mark.asyncio
async def test_get_calendar_event_unauthorized(client, auth_headers, seed_other_user):
    # Log in as other user to seed an event
    other_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "otherpassword"},
    )
    other_token = other_login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    create_resp = await client.post(
        "/api/v1/calendar/events",
        headers=other_headers,
        json={"title": "Private Event", "start_time": start.isoformat(), "end_time": end.isoformat()}
    )
    event_id = create_resp.json()["id"]

    # Try to access with main user's headers
    response = await client.get(f"/api/v1/calendar/events/{event_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Calendar event not found"

@pytest.mark.asyncio
async def test_update_calendar_event(client, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    create_resp = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={"title": "Old Event Name", "start_time": start.isoformat(), "end_time": end.isoformat()}
    )
    event_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/calendar/events/{event_id}",
        headers=auth_headers,
        json={"title": "New Event Name", "description": "Updated Description"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == "New Event Name"
    assert data["description"] == "Updated Description"

@pytest.mark.asyncio
async def test_delete_calendar_event(client, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    create_resp = await client.post(
        "/api/v1/calendar/events",
        headers=auth_headers,
        json={"title": "Disposable Event", "start_time": start.isoformat(), "end_time": end.isoformat()}
    )
    event_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=auth_headers)
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    get_resp = await client.get(f"/api/v1/calendar/events/{event_id}", headers=auth_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_google_calendar_sync(client, auth_headers):
    from unittest.mock import AsyncMock, MagicMock, patch
    import httpx
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "summary": "Synced Google Event",
                "description": "This is a synced event",
                "start": {"dateTime": "2026-07-16T12:00:00Z"},
                "end": {"dateTime": "2026-07-16T13:00:00Z"},
                "recurrence": []
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient", return_value=AsyncContextManagerMock()):
        # Verify sync works and returns success
        response = await client.post(
            "/api/v1/calendar/sync/google",
            params={"google_token": "mock_google_token"},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert "last_sync" in data
        assert data["imported_count"] == 1

    # Verify status is now synced
    status_response = await client.get("/api/v1/calendar/sync/status", headers=auth_headers)
    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["status"] == "synced"
    assert status_response.json()["last_sync"] == data["last_sync"]


@pytest.mark.asyncio
async def test_google_calendar_sync_status_never_synced(client, auth_headers):
    # Status before syncing should return never_synced
    status_response = await client.get("/api/v1/calendar/sync/status", headers=auth_headers)
    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["status"] == "never_synced"
    assert status_response.json()["last_sync"] is None

