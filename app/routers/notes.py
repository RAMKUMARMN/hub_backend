import uuid
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User
from app.schemas.notes import CreateNoteRequest, UpdateNoteRequest, NoteResponse, ShareNoteRequest
from app.services.notes_service import NotesService

router = APIRouter(prefix="/notes", tags=["notes"])

@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: CreateNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).create_note(current_user.id, body)

@router.get("/", response_model=list[NoteResponse])
async def list_notes(
    tag: str | None = Query(None, description="Filter notes by tag"),
    pinned: bool | None = Query(None, description="Filter notes by pinned status"),
    archived: bool | None = Query(None, description="Filter notes by archived status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).list_notes(current_user.id, tag, pinned, archived)

@router.get("/search", response_model=list[NoteResponse])
async def search_notes(
    q: str = Query(..., description="Query string to search in note titles/content"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).search_notes(current_user.id, q)

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).get_note(note_id, current_user.id)

@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    body: UpdateNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).update_note(note_id, current_user.id, body)

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await NotesService(db).delete_note(note_id, current_user.id)

@router.post("/{note_id}/share", response_model=NoteResponse)
async def share_note(
    note_id: uuid.UUID,
    body: ShareNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await NotesService(db).share_note(note_id, current_user.id, body.email)
