"""
app/auth — canonical authentication module.

Public API (unchanged — other services import from here):
  auth_router      — FastAPI router, mounted in app/main.py
  get_current_user — dependency for any protected endpoint
  get_current_admin — dependency for admin-only endpoints
"""
from app.auth.api.auth_routes import router as auth_router
from app.auth.security.dependencies import get_current_user, get_current_admin

__all__ = ["auth_router", "get_current_user", "get_current_admin"]
