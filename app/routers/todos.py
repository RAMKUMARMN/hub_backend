"""Todos router — /api/v1/todos/*"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.todo import Todo
from app.models.user import User
from app.services.user_notification_service import create_notification
from app.websocket_manager import manager
from app.schemas.todo import (
    CompleteToggleRequest,
    CreateTodoRequest,
    TodoResponse,
    UpdateTodoRequest,
)

router = APIRouter(prefix="/todos", tags=["todos"])


# ---------------------------
# LIST TODOS
# ---------------------------
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


# ---------------------------
# CREATE TODO
# ---------------------------
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
    reminder_at=body.reminder_at,
    reminder_sent=False,
)

    db.add(todo)
    await db.flush()

    await create_notification(
        db=db,
        user_id=current_user.id,
        title="Todo Created",
        message=f"Todo '{todo.title}' created successfully.",
        notification_type="TODO_CREATED",
    )

    await manager.send_notification(
        str(current_user.id),
        {
            "type": "TODO_CREATED",
            "title": "Todo Created",
            "message": f"Todo '{todo.title}' created successfully.",
        },
    )

    await db.commit()
    await db.refresh(todo)

    return todo


# ---------------------------
# DELETE TODO
# ---------------------------
@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == current_user.id,
        )
    )

    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    await create_notification(
        db=db,
        user_id=current_user.id,
        title="Todo Deleted",
        message=f"Todo '{todo.title}' deleted successfully.",
        notification_type="TODO_DELETED",
    )

    await manager.send_notification(
        str(current_user.id),
        {
            "type": "TODO_DELETED",
            "title": "Todo Deleted",
            "message": f"Todo '{todo.title}' deleted successfully.",
        },
    )

    db.delete(todo)
    await db.commit()


# ---------------------------
# UPDATE TODO
# ---------------------------
@router.patch("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: uuid.UUID,
    body: UpdateTodoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == current_user.id,
        )
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

    if "reminder_at" in body.model_fields_set:
        todo.reminder_at = body.reminder_at
        todo.reminder_sent = False

    await create_notification(
        db=db,
        user_id=current_user.id,
        title="Todo Updated",
        message=f"Todo '{todo.title}' updated successfully.",
        notification_type="TODO_UPDATED",
    )

    await manager.send_notification(
        str(current_user.id),
        {
            "type": "TODO_UPDATED",
            "title": "Todo Updated",
            "message": f"Todo '{todo.title}' updated successfully.",
        },
    )

    await db.commit()
    await db.refresh(todo)

    return todo


# ---------------------------
# COMPLETE / REOPEN TODO
# ---------------------------
@router.patch("/{todo_id}/complete", response_model=TodoResponse)
async def toggle_todo_completion(
    todo_id: uuid.UUID,
    body: CompleteToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == current_user.id,
        )
    )

    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.completed = body.completed

    if body.completed:
        title = "Todo Completed"
        message = f"Todo '{todo.title}' completed successfully."
        event_type = "TODO_COMPLETED"
    else:
        title = "Todo Reopened"
        message = f"Todo '{todo.title}' marked as incomplete."
        event_type = "TODO_REOPENED"

    await create_notification(
        db=db,
        user_id=current_user.id,
        title=title,
        message=message,
        notification_type=event_type,
    )

    await manager.send_notification(
        str(current_user.id),
        {
            "type": event_type,
            "title": title,
            "message": message,
        },
    )

    await db.commit()
    await db.refresh(todo)

    return todo