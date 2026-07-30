from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
)

@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    workspace = await service.create_workspace(
        current_user.id,
        body,
    )

    return workspace

@router.get(
    "/",
    response_model=list[WorkspaceResponse],
)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    return await service.list_workspaces(
        current_user.id,
    )

@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    workspace = await service.get_workspace(
        workspace_id,
        current_user.id,
    )

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    return workspace

@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    workspace = await service.get_workspace(
        workspace_id,
        current_user.id,
    )

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    return await service.update_workspace(
        workspace,
        body,
    )

@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    workspace = await service.get_workspace(
        workspace_id,
        current_user.id,
    )

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    await service.delete_workspace(workspace)

@router.get("/{workspace_id}/summary")
async def get_workspace_summary(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)

    summary = await service.get_workspace_summary(
        workspace_id,
        current_user.id,
    )

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found",
        )

    return {
        "summary": summary
    }