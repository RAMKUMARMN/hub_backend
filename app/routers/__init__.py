from app.routers.admin import router as admin_router
from app.auth import auth_router
from app.ai import chat_router
from app.routers.documents import router as documents_router
from app.routers.todos import router as todos_router
from app.routers.focus import router as focus_router
from app.routers.calendar import router as calendar_router
from app.routers.preferences import router as preferences_router
from app.routers.system import router as system_router
from app.routers.roles import router as roles_router
from app.routers.notes import router as notes_router
from app.routers.folders import router as folders_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "admin_router",
    "auth_router",
    "chat_router",
    "documents_router",
    "todos_router",
    "focus_router",
    "calendar_router",
    "preferences_router",
    "system_router",
    "roles_router",
    "notes_router",
    "folders_router",
    "dashboard_router",
]
