"""Todos router — /api/v1/todos/*"""
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.todo import Todo
from app.models.user import User

router = APIRouter(prefix="/todos", tags=["todos"])


class CreateTodoRequest(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = "medium"
    recurrence: Optional[str] = "none"


class UpdateTodoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    recurrence: Optional[str] = None


@router.get("/")
async def list_todos(
    completed: bool | None = None,
    priority: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Todo).where(Todo.user_id == current_user.id).order_by(
        Todo.pinned.desc(), Todo.created_at.desc()
    )
    if completed is not None:
        query = query.where(Todo.completed == completed)
    if priority is not None:
        query = query.where(Todo.priority == priority)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", status_code=status.HTTP_201_CREATED)
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
        recurrence=body.recurrence,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo


@router.put("/{todo_id}")
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
    if body.title is not None: todo.title = body.title
    if body.description is not None: todo.description = body.description
    if body.due_date is not None: todo.due_date = body.due_date
    if body.priority is not None: todo.priority = body.priority
    if body.recurrence is not None: todo.recurrence = body.recurrence
    await db.commit()
    await db.refresh(todo)
    return todo


@router.put("/{todo_id}/complete")
async def toggle_complete(
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
    todo.completed = not todo.completed
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


@router.get("/today")
async def get_today_todos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    result = await db.execute(
        select(Todo).where(
            Todo.user_id == current_user.id,
            Todo.due_date >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            Todo.due_date < datetime(today.year, today.month, today.day + 1, tzinfo=timezone.utc),
        )
    )
    todos = result.scalars().all()
    total = len(todos)
    completed = len([t for t in todos if t.completed])
    pending = total - completed
    high = len([t for t in todos if t.priority == "high" and not t.completed])
    return {
        "date": str(today),
        "total": total,
        "completed": completed,
        "pending": pending,
        "high_priority_pending": high,
        "todos": todos,
    }


@router.get("/upcoming")
async def get_upcoming_todos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Todo).where(
            Todo.user_id == current_user.id,
            Todo.due_date > now,
            Todo.completed == False,
        ).order_by(Todo.due_date.asc())
    )
    return result.scalars().all()


@router.get("/recurring")
async def get_recurring_todos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(
            Todo.user_id == current_user.id,
            Todo.recurrence != "none",
        )
    )
    todos = result.scalars().all()
    return {"count": len(todos), "recurring_todos": todos}


@router.put("/{todo_id}/pin")
async def toggle_pin(
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
    todo.pinned = not todo.pinned
    await db.commit()
    return {"status": "Updated", "pinned": todo.pinned, "title": todo.title}


@router.post("/{todo_id}/focus/start")
async def start_focus(
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
    if todo.focus_started_at:
        raise HTTPException(status_code=400, detail="Focus session already running")
    todo.focus_started_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "Focus started", "title": todo.title, "started_at": todo.focus_started_at}


@router.post("/{todo_id}/focus/stop")
async def stop_focus(
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
    if not todo.focus_started_at:
        raise HTTPException(status_code=400, detail="No focus session running")
    duration = int((datetime.now(timezone.utc) - todo.focus_started_at).total_seconds() / 60)
    todo.total_focus_minutes = (todo.total_focus_minutes or 0) + duration
    todo.focus_started_at = None
    await db.commit()
    return {
        "status": "Focus stopped",
        "session_minutes": duration,
        "total_focus_minutes": todo.total_focus_minutes,
    }