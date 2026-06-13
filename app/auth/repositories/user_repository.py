"""
User repository — all database queries related to the users table.

Person 1 (Registration & Login) owns this file.
Keeps SQL out of the service layer for easier testing and reuse.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by their UUID primary key."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by their email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        full_name: str,
        hashed_password: str,
        phone: str | None = None,
    ) -> User:
        """Create and persist a new user, returning the refreshed instance."""
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            phone=phone,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def save(self, user: User) -> User:
        """Persist changes to an existing user instance."""
        await self.db.commit()
        await self.db.refresh(user)
        return user
