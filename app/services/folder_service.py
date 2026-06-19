import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.folder import DocumentFolder
from app.models.document import Document
from app.schemas.folder import CreateFolderRequest

class FolderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_folder(self, user_id: uuid.UUID, body: CreateFolderRequest) -> DocumentFolder:
        folder = DocumentFolder(
            user_id=user_id,
            name=body.name
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder

    async def get_folder(self, folder_id: uuid.UUID, user_id: uuid.UUID) -> DocumentFolder:
        result = await self.db.execute(
            select(DocumentFolder).where(DocumentFolder.id == folder_id, DocumentFolder.user_id == user_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Folder not found"
            )
        return folder

    async def list_folders(self, user_id: uuid.UUID) -> list[DocumentFolder]:
        result = await self.db.execute(
            select(DocumentFolder).where(DocumentFolder.user_id == user_id).order_by(DocumentFolder.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_folder(self, folder_id: uuid.UUID, user_id: uuid.UUID) -> None:
        folder = await self.get_folder(folder_id, user_id)

        # Un-assign all documents in this folder (setting folder_id = None)
        await self.db.execute(
            update(Document).where(Document.folder_id == folder_id).values(folder_id=None)
        )
        
        await self.db.delete(folder)
        await self.db.commit()
