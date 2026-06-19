from app.auth import auth_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.todos import router as todos_router
from app.routers.admin import router as admin_router
from app.routers.poll import router as poll_router
from app.routers.focus import router as focus_router
from app.routers.calendar import router as calendar_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "chat_router",
    "documents_router",
    "todos_router",
    "admin_router",
    "poll_router",
    "focus_router",
    "calendar_router",
    "dashboard_router",
]