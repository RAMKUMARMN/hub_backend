from app.auth.api.auth_routes import router as auth_router
from app.auth.api.oauth_routes import router as oauth_router

__all__ = ["auth_router", "oauth_router"]
