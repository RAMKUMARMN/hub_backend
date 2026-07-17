from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.models.todo import Todo
from app.models.role import Role
from app.models.audit_log import AuditLog
from app.models.system_settings import SystemSettings
from app.models.user_preferences import UserPreferences
# Auth-owned models — registered here so Alembic detects them in autogenerate
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.otp import OTPCode
from app.models.focus import FocusSession, Achievement, UserAchievement
from app.models.calendar import CalendarEvent
from app.models.notes import Note
from app.models.folder import DocumentFolder
from app.models.subtask import TodoSubtask
from app.models.poll import PollResponse
from app.models.device import UserDevice

__all__ = [
    "User",
    "ChatSession",
    "ChatMessage",
    "Document",
    "Todo",
    "RefreshToken",
    "OTPCode",
    "FocusSession",
    "Achievement",
    "UserAchievement",
    "CalendarEvent",
    "Note",
    "DocumentFolder",
    "TodoSubtask",
    "Role",
    "AuditLog",
    "SystemSettings",
    "UserPreferences",
    "PollResponse",
    "UserDevice",
]

