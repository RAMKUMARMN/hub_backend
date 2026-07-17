"""Todos router — /api/v1/todos/*"""
import uuid

from app.services.dashboard_service import invalidate_dashboard_cache
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
from app.queue.producer import publish_notification_to_queue

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
            tokens = current_user.device_tokens or []
            if not tokens:
                tokens = [current_user.email or "no_token_fallback"]
            for token in tokens:
                await publish_notification_to_queue(
                    channel="push",
                    recipient=token,
                    title="Todo Reminder",
                    body=f"Reminder for your task '{todo.title}' due on {todo.due_date.isoformat() if todo.due_date else 'None'}.",
                    message_type="todo_reminder",
                    priority="medium",
                    data={"todo_id": str(todo.id)},
                )
        except Exception:
            pass

    await invalidate_dashboard_cache(current_user.id)

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
                tokens = current_user.device_tokens or []
                if not tokens:
                    tokens = [current_user.email or "no_token_fallback"]
                for token in tokens:
                    await publish_notification_to_queue(
                        channel="push",
                        recipient=token,
                        title="Todo Reminder",
                        body=f"Reminder for your task '{todo.title}' due on {todo.due_date.isoformat() if todo.due_date else 'None'}.",
                        message_type="todo_reminder",
                        priority="medium",
                        data={"todo_id": str(todo.id)},
                    )
            except Exception:
                pass

    await db.commit()
    await db.refresh(todo)
   
    await invalidate_dashboard_cache(current_user.id)
   
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
    
    await invalidate_dashboard_cache(current_user.id)
    
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

    await invalidate_dashboard_cache(current_user.id)


# Subtasks endpoints

from app.models.subtask import TodoSubtask
from app.schemas.subtask import (
    CreateSubtaskRequest,
    UpdateSubtaskRequest,
    SubtaskResponse,
)


async def verify_todo_ownership(
    todo_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession
) -> Todo:
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
    )
    todo = result.scalar_one_or_none()

    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated todo item not found or not owned by user"
        )

    return todo


@router.post(
    "/{todo_id}/subtasks",
    response_model=SubtaskResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_subtask(
    todo_id: uuid.UUID,
    body: CreateSubtaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_todo_ownership(todo_id, current_user.id, db)

    subtask = TodoSubtask(
        todo_id=todo_id,
        title=body.title,
        completed=False
    )

    db.add(subtask)
    await db.commit()
    await db.refresh(subtask)

    return subtask


@router.get("/{todo_id}/subtasks", response_model=list[SubtaskResponse])
async def list_subtasks(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_todo_ownership(todo_id, current_user.id, db)

    result = await db.execute(
        select(TodoSubtask)
        .where(TodoSubtask.todo_id == todo_id)
        .order_by(TodoSubtask.created_at.asc())
    )

    return list(result.scalars().all())


@router.put("/{todo_id}/subtasks/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(
    todo_id: uuid.UUID,
    subtask_id: uuid.UUID,
    body: UpdateSubtaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_todo_ownership(todo_id, current_user.id, db)

    result = await db.execute(
        select(TodoSubtask)
        .where(
            TodoSubtask.id == subtask_id,
            TodoSubtask.todo_id == todo_id
        )
    )

    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtask not found under this todo"
        )

    if body.title is not None:
        subtask.title = body.title

    if body.completed is not None:
        subtask.completed = body.completed

    await db.commit()
    await db.refresh(subtask)

    return subtask


@router.delete(
    "/{todo_id}/subtasks/{subtask_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_subtask(
    todo_id: uuid.UUID,
    subtask_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await verify_todo_ownership(todo_id, current_user.id, db)

    result = await db.execute(
        select(TodoSubtask)
        .where(
            TodoSubtask.id == subtask_id,
            TodoSubtask.todo_id == todo_id
        )
    )

    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtask not found under this todo"
        )

    await db.delete(subtask)
    await db.commit()