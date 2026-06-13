"""
Token service — JWT pair creation and refresh token rotation.

Person 2 (JWT & Session Management) owns this file.
Depends on: security/jwt.py, repositories/token_repository.py
"""
from app.auth.security.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.schemas.auth import TokenResponse
from app.models.user import User


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
          "is_admin": false
        }
        """
        return {
            "sub": str(user.id),
            "email": user.email,
            "is_admin": user.is_admin,
        }

    @classmethod
    def issue_pair(cls, user: User) -> TokenResponse:
        """Issue a new access + refresh token pair for the given user."""
        payload = cls.build_payload(user)
        return TokenResponse(
            access_token=create_access_token(payload),
            refresh_token=create_refresh_token(payload),
        )
