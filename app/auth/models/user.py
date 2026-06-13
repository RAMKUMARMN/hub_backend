"""
Re-export the canonical User model from app.models.user.

We re-export rather than redefine so that Alembic has a single
source of truth for the `users` table.
"""
from app.models.user import User  # noqa: F401

__all__ = ["User"]
