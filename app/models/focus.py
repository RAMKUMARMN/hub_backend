import uuid
from datetime import datetime
from sqlalchemy import Uuid, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # "focus" | "short_break" | "long_break"
    type: Mapped[str] = mapped_column(String(20), default="focus", nullable=False)
    # "started" | "paused" | "completed" | "cancelled"
    status: Mapped[str] = mapped_column(String(20), default="started", nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Pausing state helpers
    paused_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    total_paused_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=True)

    user = relationship("User")

class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    badge_url: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # "total_focus_hours" | "consecutive_sessions"
    criteria_type: Mapped[str] = mapped_column(String(50), nullable=False)
    criteria_value: Mapped[int] = mapped_column(Integer, nullable=False)

class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    achievement_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("achievements.id", ondelete="CASCADE"), primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
