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
from app.models.todo import Todo
from app.models.subtask import TodoSubtask
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
        await session.execute(text("TRUNCATE TABLE users, todos, todo_subtasks CASCADE;"))
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
            title="Main Task",
            description="Testing subtasks linkage",
            priority="medium"
        )
        session.add(todo)
        await session.commit()
        await session.refresh(todo)
        return todo

async def test_subtask_crud(client, auth_headers, seed_todo):
    todo_id = seed_todo.id

    # Create subtask
    response = await client.post(
        f"/api/v1/todos/{todo_id}/subtasks",
        json={"title": "Subtask Step 1"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    subtask_id = response.json()["id"]
    assert response.json()["title"] == "Subtask Step 1"
    assert response.json()["completed"] is False

    # List subtasks
    list_response = await client.get(f"/api/v1/todos/{todo_id}/subtasks", headers=auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()) == 1

    # Update subtask completion
    update_response = await client.put(
        f"/api/v1/todos/{todo_id}/subtasks/{subtask_id}",
        json={"completed": True, "title": "Subtask Step 1 Updated"},
        headers=auth_headers
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["completed"] is True
    assert update_response.json()["title"] == "Subtask Step 1 Updated"

    # Delete subtask
    delete_response = await client.delete(
        f"/api/v1/todos/{todo_id}/subtasks/{subtask_id}",
        headers=auth_headers
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # List subtasks (should be empty now)
    list_empty = await client.get(f"/api/v1/todos/{todo_id}/subtasks", headers=auth_headers)
    assert len(list_empty.json()) == 0

async def test_subtask_unauthorized_access(client, auth_headers, seed_todo, seed_other_user):
    todo_id = seed_todo.id
    
    # login as other user
    other_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "otherpassword"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    # Try creating subtask under seed_todo (unowned)
    response = await client.post(
        f"/api/v1/todos/{todo_id}/subtasks",
        json={"title": "Hack subtask"},
        headers=other_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
