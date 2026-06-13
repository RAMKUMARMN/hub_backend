"""
Auth models package.

User is the single source of truth from app.models.user (used by Alembic).
RefreshToken and OTP are new models owned by auth.
"""
from app.auth.models.user import User
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.otp import OTPCode

__all__ = ["User", "RefreshToken", "OTPCode"]
