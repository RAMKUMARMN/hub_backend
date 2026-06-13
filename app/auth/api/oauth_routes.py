"""
Google OAuth routes — /api/v1/auth/google/*

Person 3 (Google OAuth) owns this file.

TODO:
  GET /auth/google
    - Redirect the user to Google's OAuth consent screen.
    - Generate a random state parameter, store in session/Redis.

  GET /auth/google/callback
    - Receive the authorization code from Google.
    - Delegate to OAuthService.handle_callback(code, state).
    - Set the refresh token as an HttpOnly cookie and return the access token.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["oauth"])


@router.get("/google")
async def google_login():
    """Redirect to Google OAuth consent screen. (Person 3 — TODO)"""
    return {"detail": "Google OAuth not yet implemented"}


@router.get("/google/callback")
async def google_callback(code: str | None = None, state: str | None = None):
    """Handle Google OAuth callback. (Person 3 — TODO)"""
    return {"detail": "Google OAuth callback not yet implemented"}
