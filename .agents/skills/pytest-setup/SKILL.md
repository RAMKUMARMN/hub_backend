---
name: pytest-setup
description: Write tests for FastAPI endpoints using pytest, httpx.AsyncClient, and SQLAlchemy async session fixtures.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# pytest for FastAPI Backend

## Contents
- [Test File Structure](#test-file-structure)
- [Fixtures](#fixtures)
- [Endpoint Tests](#endpoint-tests)
- [Service Tests](#service-tests)
- [Running Tests](#running-tests)

## Test File Structure

```
tests/
├── conftest.py              # Shared fixtures (db session, async client, auth)
├── test_auth.py             # Auth endpoint tests
├── test_todos.py            # Todo CRUD endpoint tests
├── test_chat.py             # Chat endpoint tests
├── test_documents.py        # Document upload endpoint tests
├── test_poll.py             # Poll endpoint tests
├── test_admin.py            # Admin endpoint tests
└── test_services/           # Service unit tests
    ├── test_auth_service.py
    └── test_llm_service.py
```

## Fixtures (`conftest.py`)

```python
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "TestPass123!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

## Endpoint Tests

```python
# tests/test_todos.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_todo(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.post(
        "/api/v1/todos",
        json={"title": "Buy groceries", "description": "Milk, eggs, bread"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Buy groceries"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_todos(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get("/api/v1/todos", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_unauthorized_returns_401(async_client: AsyncClient):
    response = await async_client.get("/api/v1/todos")
    assert response.status_code == 401
```

## Service Tests

```python
# tests/test_services/test_auth_service.py
import pytest

from app.services.auth_service import hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("MySecret123!")
    assert verify_password("MySecret123!", hashed) is True
    assert verify_password("WrongPassword", hashed) is False
```

## Running Tests

```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_todos.py -q

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run with database URL override
DATABASE_URL=sqlite+aiosqlite:///test.db pytest -q
```
