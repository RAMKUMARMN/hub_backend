import uuid
from datetime import datetime

from sqlalchemy import Uuid, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.role import JSONBType

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    resource: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    details: Mapped[dict] = mapped_column(
        "metadata",
        JSONBType,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )