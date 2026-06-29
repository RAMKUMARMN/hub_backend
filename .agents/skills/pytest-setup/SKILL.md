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
├── test_workspaces.py       # Workspace endpoint tests
├── test_chat.py             # Chat endpoint tests
└── test_services/           # Service unit tests
    ├── test_workspace_service.py
    └── test_notification_service.py
```

## Fixtures (`conftest.py`)

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_session

from app.database import Base
from app.main import app
from app.dependencies import get_db


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session(engine) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    # Register user and get token
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "TestPass123!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

## Endpoint Tests

```python
# tests/test_workspaces.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_workspace(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "My Workspace", "description": "Test"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Workspace"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_workspaces(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get("/api/v1/workspaces", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_unauthorized_returns_401(async_client: AsyncClient):
    response = await async_client.get("/api/v1/workspaces")
    assert response.status_code == 401
```

## Service Tests

```python
# tests/test_services/test_workspace_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.services import workspace_service


@pytest.mark.asyncio
async def test_create_workspace_service(db_session: AsyncSession):
    workspace = await workspace_service.create_workspace(
        db_session,
        {"name": "Test", "description": None},
        "user-id-123",
    )
    assert workspace.name == "Test"
    assert workspace.owner_id == "user-id-123"
```

## Running Tests

```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_workspaces.py -q

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run with database URL override
DATABASE_URL=sqlite+aiosqlite:///test.db pytest -q
```
