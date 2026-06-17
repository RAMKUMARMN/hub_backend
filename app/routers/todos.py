"""Todos router — /api/v1/todos/*"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.todo import Todo
from app.models.user import User
from app.schemas.todo import (
    CompleteToggleRequest,
    CreateTodoRequest,
    TodoResponse,
    UpdateTodoRequest,
)

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("/", response_model=list[TodoResponse])
async def list_todos(
    completed: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Todo).where(Todo.user_id == current_user.id).order_by(Todo.created_at.desc())
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
        due_date=body.due_date,
    )

    db.add(todo)
    await db.commit()
    await db.refresh(todo)

    try:
        async with httpx.AsyncClient(
        base_url=settings.notify_service_url,
        timeout=30,
        ) as client:
             await client.post(
            "/api/v1/notify/send",
            json={
                "channel": "email",
                "recipient": current_user.email,
                "subject": "Todo Created",
                "body": f"Your todo '{todo.title}' has been created successfully.",
            },
        )
    except Exception:
        pass

    async with httpx.AsyncClient(
        base_url=settings.notify_service_url,
        timeout=30,
    ) as client:
        await client.post(
            "/api/v1/notify/send",
            json={
                "channel": "email",
                "recipient": current_user.email,
                "subject": "Todo Created",
                "body": f"Your todo '{todo.title}' has been created successfully.",
            },
        )

    return todo

@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == current_user.id)
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    await db.delete(todo)
    await db.commit()
