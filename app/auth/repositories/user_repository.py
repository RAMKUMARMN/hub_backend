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
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        full_name: str,
        hashed_password: str,
        phone: str | None = None,
        status: str = "pending",
        is_active: bool = False,
    ) -> User:
        """Create and persist a new user, returning the refreshed instance."""
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            phone=phone,
            status=status,
            is_active=is_active,
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

    async def get_pending_users(self):
        result = await self.db.execute(
            select(User).where(User.status == "pending")
        )
        return result.scalars().all()

    async def approve_user(self, user_id):
        user = await self.get_by_id(user_id)

        if not user:
            return None

        user.status = "active"
        user.is_active = True

        await self.db.commit()
        await self.db.refresh(user)

        return user