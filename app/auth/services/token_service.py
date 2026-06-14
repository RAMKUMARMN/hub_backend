"""
Token service — JWT pair creation and refresh token rotation.

Person 2 (JWT & Session Management) owns this file.
Depends on: security/jwt.py, repositories/token_repository.py
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.token_repository import TokenRepository
from app.auth.security.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.schemas.auth import TokenResponse
from app.auth.security.roles import UserRole, UserStatus
from app.models.user import User
from app.config import settings


class TokenService:
    """
    Wraps JWT creation so that route handlers receive a TokenResponse
    directly without importing low-level jwt helpers.

    TODO (token rotation):
      - Store hashed refresh token via TokenRepository on issue.
      - Validate DB record on /refresh (not just JWT signature).
      - Revoke old token on rotation and on /logout.
    """

    @staticmethod
    def build_payload(user: User) -> dict:
        """
        Build the standard JWT payload agreed by all 4 developers.

        {
          "sub":      "<uuid>",
          "email":    "user@tkmce.ac.in",
          "role":     "user",
          "status":   "active"
        }
        """
        role = UserRole.ADMIN.value if user.is_admin else UserRole.USER.value
        status_val = UserStatus.ACTIVE.value if user.is_active else UserStatus.SUSPENDED.value

        return {
            "sub": str(user.id),
            "email": user.email,
            "role": role,
            "status": status_val,
        }

    @classmethod
    async def issue_pair(cls, user: User, db: AsyncSession) -> TokenResponse:
        """Issue a new access + refresh token pair for the given user."""
        payload = cls.build_payload(user)
        
        refresh_payload = payload.copy()
        refresh_payload["jti"] = str(uuid.uuid4())
        
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(refresh_payload)

        # Hash and store refresh token
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        
        repo = TokenRepository(db)
        await repo.store(user_id=user.id, token_hash=token_hash, expires_at=expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )
