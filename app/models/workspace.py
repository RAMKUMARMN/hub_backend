import uuid


from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum

class WorkspaceType(str, Enum):
    GENERAL = "general"
    PROJECT = "project"

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    type: Mapped[WorkspaceType] = mapped_column(
    SQLEnum(WorkspaceType),
    default=WorkspaceType.PROJECT,
    nullable=False,
)

    icon: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="📁",
    )

    color: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="#2196F3",
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner = relationship("User", back_populates="workspaces")

    documents = relationship(
        "Document",
        back_populates="workspace",
    )

    notes = relationship(
        "Note",
        back_populates="workspace",
    )

    todos = relationship(
        "Todo",
        back_populates="workspace",
    )