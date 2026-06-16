"""Todos router — /api/v1/todos/*"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.todo import Todo
from app.models.user import User
from app.schemas.todo import (
    CompleteToggleRequest,
    CreateTodoRequest,
    TodoResponse,
    UpdateTodoRequest,
)
from app.queue.producer import publish_todo_reminder

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
        priority=body.priority,
        reminder_time=body.reminder_time,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)

    if todo.reminder_time:
        try:
            await publish_todo_reminder({
                "user_id": str(current_user.id),
                "todo_id": str(todo.id),
                "title": todo.title,
                "reminder_time": todo.reminder_time.isoformat()
            })
        except Exception:
            pass

    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: uuid.UUID,
    body: UpdateTodoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == current_user.id)
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if body.title is not None:
        todo.title = body.title
    if body.description is not None:
        todo.description = body.description
    if body.due_date is not None:
        todo.due_date = body.due_date
    if body.priority is not None:
        todo.priority = body.priority
    
    old_reminder = todo.reminder_time
    if body.reminder_time is not None:
        todo.reminder_time = body.reminder_time
        if todo.reminder_time and todo.reminder_time != old_reminder:
            try:
                await publish_todo_reminder({
                    "user_id": str(current_user.id),
                    "todo_id": str(todo.id),
                    "title": todo.title,
                    "reminder_time": todo.reminder_time.isoformat()
                })
            except Exception:
                pass

    await db.commit()
    await db.refresh(todo)
    return todo


@router.put("/{todo_id}/complete", response_model=TodoResponse)
async def toggle_complete(
    todo_id: uuid.UUID,
    body: CompleteToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == current_user.id)
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.completed = body.completed
    await db.commit()
    await db.refresh(todo)
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
