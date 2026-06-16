"""
Password reset service — email-based password recovery flow.

Person 4 (OTP & Password Recovery) owns this file.
"""
from datetime import datetime, timedelta, timezone
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from app.auth.repositories.user_repository import UserRepository
from app.auth.security.password import hash_password
from app.auth.security.jwt import decode_token
from app.auth.utils.email import send_password_reset_email
from app.config import settings


class PasswordResetService:
    @staticmethod
    async def send_reset_email(db: AsyncSession, email: str) -> None:
        """
        Look up user by email and send a secure password reset link.
        Silently returns if the email does not exist to prevent enumeration.
        """
        user_repo = UserRepository(db)
        user = await user_repo.get_by_email(email)
        if not user:
            # Silent return to prevent email enumeration
            return

        if user.status == "suspended":
            # Silently ignore suspended users to prevent enumeration, or raise error. 
            # We silently return here to match standard privacy flow.
            return

        # Create a signed stateless JWT token.
        # We embed the first 10 characters of the current hashed_password.
        # If the password changes, the hash segment changes, which invalidates the token.
        pwd_hash_segment = user.hashed_password[:10]
        payload = {
            "sub": str(user.id),
            "purpose": "password_reset",
            "hash": pwd_hash_segment,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        
        # Link points to Next.js frontend port (3000 by default or configured)
        reset_link = f"http://localhost:3000/auth/reset-password?token={token}"
        await send_password_reset_email(user.email, reset_link)

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
        """
        Validate the stateless token and update the user's password.
        Throws 400 Bad Request if the token is invalid, expired, or already used.
        """
        try:
            payload = decode_token(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset link"
            )

        if payload.get("purpose") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset link"
            )

        user_id = payload.get("sub")
        token_hash = payload.get("hash")
        if not user_id or not token_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset link"
            )

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset link"
            )

        if user.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended"
            )

        # Single-use check: Verify the password has not been updated since token creation
        if user.hashed_password[:10] != token_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password reset link has already been used"
            )

        # Hash and persist new password
        user.hashed_password = hash_password(new_password)
        await user_repo.save(user)
