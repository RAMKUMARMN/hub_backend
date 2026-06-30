from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories.user_repository import UserRepository
from app.auth.services.token_service import TokenService
from app.auth.security.password import hash_password


class OAuthService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def handle_google_user(
        self,
        email: str,
        full_name: str,
    ):

        user = await self.user_repo.get_by_email(email)

        if not user:
            is_active = True
            status_val = "active" if email.endswith("@tkmce.ac.in") else "pending"
            user = await self.user_repo.create(
                email=email,
                full_name=full_name,
                hashed_password=hash_password("oauth-user"),
                phone=None,
                is_active=is_active,
                status=status_val,
            )

        if user.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending admin approval",
            )
        elif user.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account suspended",
            )

        return await TokenService.issue_pair(
            user,
            self.db
        )