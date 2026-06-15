from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.documents import router as documents_router
from app.routers.todos import router as todos_router
from app.routers.admin import router as admin_router
from app.routers.poll import router as poll_router
from app.routers.n8n_test import router as n8n_test_router

__all__ = ["auth_router", "chat_router", "documents_router", "todos_router", "admin_router", "poll_router", "n8n_test_router"]
