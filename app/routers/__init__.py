from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.todos import router as todos_router
from app.routers.admin import router as admin_router
from app.routers.poll import router as poll_router
from app.routers.notification_jobs import router as notification_jobs_router
from app.routers.audit import router as audit_router

__all__ = [
    "auth_router",
    "chat_router",
    "documents_router",
    "notification_jobs_router",
    "todos_router",
    "admin_router",
    "poll_router",
    "audit_router",
]