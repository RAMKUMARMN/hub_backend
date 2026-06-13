"""
Auth service — registration and login business logic.

Person 1 (Registration & Login) owns this file.
Depends on: UserRepository, password.py, token_service.py
"""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.user_repository import UserRepository
from app.auth.security.password import hash_password, verify_password
from app.auth.schemas.auth import RegisterRequest, TokenResponse
from app.models.user import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, body: RegisterRequest) -> User:
        """
        Register a new user.

        Raises 400 if the email is already taken.
        TODO: Add @tkmce.ac.in domain restriction (see utils/validators.py).
        TODO: Send verification OTP after creation (wire up OTPService).
        """
        existing = await self.user_repo.get_by_email(body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        return await self.user_repo.create(
            email=body.email,
            full_name=body.full_name,
            hashed_password=hash_password(body.password),
            phone=body.phone,
        )

    async def login(self, email: str, password: str) -> User:
        """
        Verify credentials and return the authenticated User.

        Raises 401 if credentials are invalid.
        TODO: Check user.status == "active" (not "pending" or "suspended").
        """
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return user
