import uuid
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.notes import Note
from app.models.user import User
from app.schemas.notes import CreateNoteRequest, UpdateNoteRequest

class NotesService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_note(self, user_id: uuid.UUID, body: CreateNoteRequest) -> Note:
        note = Note(
            user_id=user_id,
            title=body.title,
            content=body.content,
            tags=body.tags,
            is_pinned=body.is_pinned,
            is_archived=body.is_archived
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def get_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note:
        result = await self.db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found"
            )
        return note

    async def list_notes(
        self,
        user_id: uuid.UUID,
        tag: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None
    ) -> list[Note]:
        query = select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
        
        if tag:
            # Postgres ARRAY overlap or contains check
            query = query.where(Note.tags.any(tag))
        if pinned is not None:
            query = query.where(Note.is_pinned == pinned)
        if archived is not None:
            query = query.where(Note.is_archived == archived)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_note(self, note_id: uuid.UUID, user_id: uuid.UUID, body: UpdateNoteRequest) -> Note:
        note = await self.get_note(note_id, user_id)

        if body.title is not None:
            note.title = body.title
        if body.content is not None:
            note.content = body.content
        if body.tags is not None:
            note.tags = body.tags
        if body.is_pinned is not None:
            note.is_pinned = body.is_pinned
        if body.is_archived is not None:
            note.is_archived = body.is_archived

        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def delete_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None:
        note = await self.get_note(note_id, user_id)
        await self.db.delete(note)
        await self.db.commit()

    async def search_notes(self, user_id: uuid.UUID, query_str: str) -> list[Note]:
        if not query_str:
            return await self.list_notes(user_id)
            
        pattern = f"%{query_str}%"
        query = select(Note).where(
            Note.user_id == user_id,
            or_(
                Note.title.ilike(pattern),
                Note.content.ilike(pattern)
            )
        ).order_by(Note.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def share_note(self, note_id: uuid.UUID, user_id: uuid.UUID, target_email: str) -> Note:
        note = await self.get_note(note_id, user_id)

        # Find the target user
        result = await self.db.execute(
            select(User).where(User.email == target_email)
        )
        target_user = result.scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found"
            )

        # Create a copy of the note for the target user
        shared_note = Note(
            user_id=target_user.id,
            title=f"{note.title} (Shared)",
            content=note.content,
            tags=note.tags,
            is_pinned=False,
            is_archived=False
        )
        self.db.add(shared_note)
        await self.db.commit()
        await self.db.refresh(shared_note)
        return shared_note
