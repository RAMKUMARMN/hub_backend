from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import httpx
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload["type"] = "access"
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


async def verify_google_token(id_token: str) -> dict[str, Any] | None:
    """
    Verify Google ID token via Google's OAuth2 API.
    Returns payload if valid, otherwise None.
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

