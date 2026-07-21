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
├── poll.py            # Poll/survey responses
├── documents.py       # File upload and management
└── admin.py           # Admin operations (bulk user create)
```

Each router file registers a sub-prefix. `app/main.py` applies the global `/api/v1` prefix:

```python
PREFIX = "/api/v1"
app.include_router(auth_router, prefix=PREFIX)
app.include_router(todos_router, prefix=PREFIX)
```

Router files define only the sub-path:

```python
router = APIRouter(prefix="/todos", tags=["todos"])
```

## Endpoint Template

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.todo import Todo
from app.models.user import User
from app.schemas.todo import CreateTodoRequest, TodoResponse

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("/", response_model=list[TodoResponse])
async def list_todos(
    completed: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Todo)
        .where(Todo.user_id == current_user.id)
        .order_by(Todo.created_at.desc())
    )
    if completed is not None:
        query = query.where(Todo.completed == completed)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: CreateTodoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    todo = Todo(
        user_id=current_user.id,
        title=body.title,
        description=body.description,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo
```

## Pydantic Schemas

```python
# app/schemas/todo.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CreateTodoRequest(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None


class TodoResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    completed: bool
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

## Dependencies

### Database session

```python
# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Authentication

```python
# app/dependencies.py
from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_token


async def get_current_user(
    token: str = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token.credentials)
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

## Error Handling

Use consistent error responses raised inline in handlers:

```python
from fastapi import HTTPException, status

# Not found
raise HTTPException(status_code=404, detail="Todo not found")

# Forbidden
raise HTTPException(status_code=403, detail="Not authorized")

# Validation (handled automatically by Pydantic → 422)
```

## Testing

```python
# tests/test_todos.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_list_todos_returns_200(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/todos", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## Verification

1. `ruff check app/routers/<domain>.py` — lint clean
2. `python -c "from app.main import app"` — imports resolve
3. Start server (`uvicorn app.main:app --reload`) and hit endpoint with `curl` or httpie
