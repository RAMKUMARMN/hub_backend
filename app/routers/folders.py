import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User
from app.schemas.folder import CreateFolderRequest, FolderResponse
from app.services.folder_service import FolderService

router = APIRouter(prefix="/document-folders", tags=["document-folders"])

@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FolderService(db).create_folder(current_user.id, body)

@router.get("/", response_model=list[FolderResponse])
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FolderService(db).list_folders(current_user.id)

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await FolderService(db).delete_folder(folder_id, current_user.id)
