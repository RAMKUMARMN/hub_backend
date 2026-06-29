---
name: fastapi-endpoint-setup
description: Create REST endpoints with FastAPI following the project's conventions: router files, Pydantic schemas, dependency injection, and httpx tests.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# FastAPI Endpoint Setup

## Contents
- [Router Structure](#router-structure)
- [Endpoint Template](#endpoint-template)
- [Pydantic Schemas](#pydantic-schemas)
- [Dependencies](#dependencies)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Verification](#verification)

## Router Structure

```
app/routers/
├── __init__.py
├── auth.py            # Login, register, token refresh
├── chat.py            # Chat messages, conversations
├── todos.py           # Todo CRUD
├── workspaces.py      # Workspace management
└── notifications.py   # Notification endpoints
```

Each router file registers endpoints. The router is included in `app/main.py` via:

```python
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
```

## Endpoint Template

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead
from app.models.user import User
from app.services import workspace_service

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.get("/", response_model=list[WorkspaceRead])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspaces = await workspace_service.get_workspaces(db, current_user.id)
    return workspaces


@router.post("/", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await workspace_service.create_workspace(db, data, current_user.id)
    return workspace
```

## Pydantic Schemas

```python
# app/schemas/workspace.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
```

## Dependencies

### Database session

```python
# app/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### Authentication

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_jwt(token)
    user = await user_service.get_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

## Error Handling

Use consistent error responses:

```python
from fastapi import HTTPException, status

# Not found
raise HTTPException(status_code=404, detail="Workspace not found")

# Forbidden
raise HTTPException(status_code=403, detail="Not authorized")

# Validation (handled automatically by Pydantic → 422)
```

## Testing

```python
# tests/test_workspaces.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_list_workspaces_returns_200(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/workspaces", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## Verification

1. `ruff check app/routers/<domain>.py` — lint clean
2. `python -c "from app.main import app"` — imports resolve
3. `pytest tests/test_<domain>.py -q` — tests pass
4. Start server and hit endpoint with `curl` or httpie
