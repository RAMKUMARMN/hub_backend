"""
Backward-compat shim — auth dependencies have moved to app.auth.dependencies.
Import from there directly in new code.
"""
from app.auth.dependencies import get_current_admin, get_current_user  # noqa: F401

__all__ = ["get_current_user", "get_current_admin"]
