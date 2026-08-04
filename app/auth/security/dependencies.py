"""
FastAPI dependency injectors for authentication and authorization.

Person 2 (JWT & Session Management) owns this file.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth.security.jwt import decode_token

# auto_error=False so we can return 401 instead of FastAPI's default 403
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and return the currently authenticated user from the Bearer token."""
    from app.config import settings
    if settings.debug:
        result = await db.execute(select(User))
        # user = result.scalars().first()
        user = result.scalar_one_or_none()

        print("DB USER:", user)

        if user:
            print("ACTIVE:", user.is_active)

        if user is None:
            user = User(
                email="dev@tkmce.ac.in",
                full_name="Developer Mode",
                hashed_password="mock",
                status="active",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        print("❌ No Authorization header received")
        raise credentials_exception

    token = credentials.credentials
    print("TOKEN:", token[:40], "...")

    try:
        payload = decode_token(token)
        print("PAYLOAD:", payload)

        if payload.get("type") != "access":
            print("❌ Wrong token type:", payload.get("type"))
            raise credentials_exception

        user_id = payload.get("sub")
        print("SUB:", user_id)

        if user_id is None:
            print("❌ Missing sub claim")
            raise credentials_exception

    except JWTError as e:
        print("❌ JWT ERROR:", repr(e))
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )

    user = result.scalar_one_or_none()

    print("USER:", user)

    if user:
        print("ACTIVE:", user.is_active)

    if user is None or not user.is_active:
        print("❌ User not found or inactive")
        raise credentials_exception

    return user


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Check admin privileges directly from JWT without a DB lookup."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        
        # Check role directly from token payload
        if payload.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        
        return payload
    except JWTError:
        raise credentials_exception
