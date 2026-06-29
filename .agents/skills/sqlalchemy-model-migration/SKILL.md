---
name: sqlalchemy-model-migration
description: Create SQLAlchemy 2.0 async models and Alembic migrations following the project's conventions: UUID PKs, timestamps, soft deletes, and Pydantic schemas.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# SQLAlchemy Models & Migrations

## Contents
- [Model Template](#model-template)
- [Relationships](#relationships)
- [Timestamps Mixin](#timestamps-mixin)
- [Alembic Migration](#alembic-migration)
- [Pydantic Schemas](#pydantic-schemas)
- [Verification](#verification)

## Model Template

```python
# app/models/workspace.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", back_populates="workspaces")
```

## Relationships

```python
# One-to-many
owner = relationship("User", back_populates="workspaces")

# Many-to-many via association table
workspace_members = Table(
    "workspace_members",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id")),
    Column("workspace_id", UUID(as_uuid=True), ForeignKey("workspaces.id")),
)
```

## Timestamps Mixin

```python
# app/models/mixins.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

## Alembic Migration

Generate: `alembic revision --autogenerate -m "add workspaces table"`

Review the generated file in `alembic/versions/`:

```python
"""add workspaces table

Revision ID: abc123
Revises: def456
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
    )


def downgrade():
    op.drop_table("workspaces")
```

Apply: `alembic upgrade head`  
Rollback: `alembic downgrade -1`

## Pydantic Schemas

```python
# app/schemas/workspace.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
```

## Verification

1. `python -c "from app.models.workspace import Workspace"` — model imports
2. `alembic revision --autogenerate -m "test"` — migration generates
3. `alembic upgrade head` — migration applies cleanly
4. `alembic downgrade -1` — migration rolls back cleanly
5. `python -c "from app.schemas.workspace import WorkspaceCreate, WorkspaceRead"` — schemas import
