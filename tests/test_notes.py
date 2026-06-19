import pytest
import pytest_asyncio
import uuid

pytestmark = pytest.mark.asyncio

from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.notes import Note
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
        await session.execute(text("TRUNCATE TABLE users, notes CASCADE;"))
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

async def test_create_note(client, auth_headers):
    response = await client.post(
        "/api/v1/notes/",
        json={"title": "Test Title", "content": "Test Content", "tags": ["tag1", "tag2"], "is_pinned": True},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Test Title"
    assert data["content"] == "Test Content"
    assert "tag1" in data["tags"]
    assert data["is_pinned"] is True

async def test_list_and_filter_notes(client, auth_headers, seed_user):
    async with AsyncSessionLocal() as session:
        n1 = Note(user_id=seed_user.id, title="Note 1", content="Content 1", tags=["study"], is_pinned=True)
        n2 = Note(user_id=seed_user.id, title="Note 2", content="Content 2", tags=["work"], is_pinned=False)
        session.add_all([n1, n2])
        await session.commit()

    # Get all notes
    response = await client.get("/api/v1/notes/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2

    # Filter by pinned
    response = await client.get("/api/v1/notes/", params={"pinned": True}, headers=auth_headers)
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Note 1"

    # Filter by tag
    response = await client.get("/api/v1/notes/", params={"tag": "work"}, headers=auth_headers)
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Note 2"

async def test_search_notes(client, auth_headers, seed_user):
    async with AsyncSessionLocal() as session:
        n1 = Note(user_id=seed_user.id, title="Lecture Notes", content="Math session", tags=[])
        n2 = Note(user_id=seed_user.id, title="Shopping list", content="Groceries and milk", tags=[])
        session.add_all([n1, n2])
        await session.commit()

    # Search for "math"
    response = await client.get("/api/v1/notes/search", params={"q": "math"}, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Lecture Notes"

    # Search for "groceries"
    response = await client.get("/api/v1/notes/search", params={"q": "groceries"}, headers=auth_headers)
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Shopping list"

async def test_update_and_delete_note(client, auth_headers, seed_user):
    async with AsyncSessionLocal() as session:
        n = Note(user_id=seed_user.id, title="Update Me", content="Original", tags=[])
        session.add(n)
        await session.commit()
        await session.refresh(n)
        note_id = n.id

    # Update note
    response = await client.put(
        f"/api/v1/notes/{note_id}",
        json={"title": "Updated Title", "content": "Updated Content"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Updated Title"

    # Delete note
    delete_response = await client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Get single note (should be 404)
    get_response = await client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

async def test_share_note(client, auth_headers, seed_user, seed_other_user):
    async with AsyncSessionLocal() as session:
        n = Note(user_id=seed_user.id, title="Secret Document", content="Top secret info", tags=["confidential"])
        session.add(n)
        await session.commit()
        await session.refresh(n)
        note_id = n.id

    # Share with other user
    response = await client.post(
        f"/api/v1/notes/{note_id}/share",
        json={"email": "other@example.com"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "Secret Document" in data["title"]
    assert data["user_id"] == str(seed_other_user.id)
