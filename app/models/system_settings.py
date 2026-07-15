import uuid
from datetime import datetime

from sqlalchemy import Uuid, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.role import JSONBType

from app.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    value: Mapped[dict] = mapped_column(
        JSONBType,
        default=dict,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )