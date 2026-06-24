"""
JWT token creation and verification.

Person 2 (JWT & Session Management) owns this file.

JWT Payload contract (agreed by all 4 devs):
{
  "sub":    "user-uuid",
  "email":  "user@tkmce.ac.in",
  "role":   "user",
  "status": "active",
  "exp":    <unix timestamp>
}
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import jwt

from app.config import settings



def create_access_token(data: dict[str, Any]) -> str:
    """Create a short-lived access token (default: 30 min)."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload["type"] = "access"
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a long-lived refresh token (default: 7 days)."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jose.JWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def verify_token(token: str) -> dict[str, Any] | None:
    """
    Helper to verify and decode a token without throwing exceptions.
    Returns the payload dictionary if valid, or None if invalid or expired.
    """
    from jose import JWTError
    try:
        return decode_token(token)
    except JWTError:
        return None


async def verify_google_token(id_token: str) -> dict[str, Any] | None:
    """
    Verify Google ID token via Google's OAuth2 tokeninfo API.
    Returns the user info payload if valid, otherwise None.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
                timeout=10
            )
            if response.status_code != 200:
                return None

            payload = response.json()
            aud = payload.get("aud")

            # Verify the audience matches our google_client_id if configured
            if settings.google_client_id and aud != settings.google_client_id:
                return None

            return payload
        except Exception:
            return None

