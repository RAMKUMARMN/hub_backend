import uuid
from datetime import datetime

from sqlalchemy import Uuid, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.role import JSONBType

from app.database import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    theme: Mapped[str] = mapped_column(
        String(20),
        default="light",
    )

    notification_settings: Mapped[dict] = mapped_column(
        JSONBType,
        default=dict,
    )

    security_settings: Mapped[dict] = mapped_column(
        JSONBType,
        default=dict,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )