from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceSummary
from app.models.document import Document
from app.models.notes import Note
from app.models.todo import Todo


class WorkspaceService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workspace(
        self,
        owner_id: UUID,
        data: WorkspaceCreate,
    ) -> Workspace:

        workspace = Workspace(
            owner_id=owner_id,
            **data.model_dump(),
        )

        self.db.add(workspace)

        await self.db.commit()

        await self.db.refresh(workspace)

        return workspace

    async def list_workspaces(
        self,
        owner_id: UUID,
    ):

        result = await self.db.execute(

            select(Workspace)

            .where(
                Workspace.owner_id == owner_id
            )

            .order_by(
                Workspace.created_at.desc()
            )
        )

        return result.scalars().all()

    async def get_workspace(
        self,
        workspace_id: UUID,
        owner_id: UUID,
    ):

        result = await self.db.execute(

            select(Workspace)

            .where(
                Workspace.id == workspace_id,
                Workspace.owner_id == owner_id,
            )
        )

        return result.scalar_one_or_none()

    async def update_workspace(
        self,
        workspace: Workspace,
        data: WorkspaceUpdate,
    ):

        for field, value in data.model_dump(
            exclude_unset=True
        ).items():

            setattr(workspace, field, value)

        await self.db.commit()

        await self.db.refresh(workspace)

        return workspace

    async def delete_workspace(
        self,
        workspace: Workspace,
    ):

        await self.db.delete(workspace)

        await self.db.commit()

    async def get_workspace_summary(
        self,
        workspace_id: UUID,
        owner_id: UUID,
    ) -> WorkspaceSummary:

        workspace = await self.get_workspace(
            workspace_id,
            owner_id,
        )

        if workspace is None:
            return None

        documents = await self.db.scalar(
            select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id
            )
        )

        notes = await self.db.scalar(
            select(func.count(Note.id)).where(
                Note.workspace_id == workspace_id
            )
        )

        todos = await self.db.scalar(
            select(func.count(Todo.id)).where(
                Todo.workspace_id == workspace_id
            )
        )

        completed_todos = await self.db.scalar(
            select(func.count(Todo.id)).where(
                Todo.workspace_id == workspace_id,
                Todo.completed.is_(True),
            )
        )

        pending_todos = await self.db.scalar(
            select(func.count(Todo.id)).where(
                Todo.workspace_id == workspace_id,
                Todo.completed.is_(False),
            )
        )

        return WorkspaceSummary(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            documents=documents or 0,
            notes=notes or 0,
            todos=todos or 0,
            completed_todos=completed_todos or 0,
            pending_todos=pending_todos or 0,
        )
        
        