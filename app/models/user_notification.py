from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    todo_id = Column(UUID(as_uuid=True), ForeignKey("todos.id"), nullable=True)

    title = Column(String, nullable=False)

    message = Column(String, nullable=False)

    notification_type = Column(String, nullable=False)

    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Optional relationships (helpful for ORM queries)
    user = relationship("User", backref="notifications")
    todo = relationship("Todo", backref="notifications")