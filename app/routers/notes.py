import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.note import Note
from app.models.user import User
from app.models.todo import Todo

router = APIRouter(prefix="/notes", tags=["Notes"])


class NoteCreateSchema(BaseModel):
    title: str
    content: str
    tags: Optional[str] = None


class NoteUpdateSchema(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None


@router.get("/")
async def get_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(Note.user_id == current_user.id)
        .order_by(Note.pinned.desc(), Note.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/")
async def create_note(
    note: NoteCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_note = Note(
        user_id=current_user.id,
        title=note.title,
        content=note.content,
        tags=note.tags
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    return new_note


@router.get("/recent")
async def get_recent_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(Note.user_id == current_user.id)
        .order_by(Note.updated_at.desc()).limit(5)
    )
    return {"recent_notes": result.scalars().all()}


@router.get("/pinned")
async def get_pinned_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.user_id == current_user.id,
            Note.pinned == True
        )
    )
    return {"pinned_notes": result.scalars().all()}


@router.get("/search")
async def search_notes(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.user_id == current_user.id,
            or_(
                Note.title.ilike(f"%{q}%"),
                Note.content.ilike(f"%{q}%"),
                Note.tags.ilike(f"%{q}%")
            )
        )
    )
    notes = result.scalars().all()
    return {"query": q, "count": len(notes), "results": notes}


@router.get("/tag")
async def get_by_tag(
    tag: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.user_id == current_user.id,
            Note.tags.ilike(f"%{tag}%")
        )
    )
    notes = result.scalars().all()
    return {"tag": tag, "count": len(notes), "notes": notes}


@router.get("/{note_id}")
async def get_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == current_user.id
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return note


@router.put("/{note_id}")
async def update_note(
    note_id: uuid.UUID,
    updates: NoteUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == current_user.id
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    if updates.title: note.title = updates.title
    if updates.content: note.content = updates.content
    if updates.tags is not None: note.tags = updates.tags
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}")
async def delete_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == current_user.id
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    await db.delete(note)
    await db.commit()
    return {"status": "Deleted", "message": "Note removed successfully."}


@router.put("/{note_id}/pin")
async def toggle_pin(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == current_user.id
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    note.pinned = not note.pinned
    await db.commit()
    return {"status": "Updated", "pinned": note.pinned, "title": note.title}


@router.post("/{note_id}/convert-to-todo")
async def convert_to_todo(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note).where(
            Note.id == note_id,
            Note.user_id == current_user.id
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    new_todo = Todo(
        user_id=current_user.id,
        title=note.title,
        description=note.content[:200],
        priority="medium"
    )
    db.add(new_todo)
    await db.commit()
    await db.refresh(new_todo)
    return {
        "status": "Converted",
        "message": "Note converted to todo successfully!",
        "todo": new_todo
    }