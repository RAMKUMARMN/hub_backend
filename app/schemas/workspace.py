from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.workspace import WorkspaceType


class WorkspaceBase(BaseModel):
    name: str
    type: WorkspaceType = WorkspaceType.PROJECT
    icon: str = "📁"
    color: str = "#2196F3"


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    type: WorkspaceType | None = None
    icon: str | None = None
    color: str | None = None


class WorkspaceResponse(WorkspaceBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WorkspaceSummary(BaseModel):
    workspace_id: UUID
    workspace_name: str
    documents: int
    notes: int
    todos: int
    completed_todos: int
    pending_todos: int