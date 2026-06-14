"""
Token repository — stores and validates refresh tokens in the database.

Person 2 (JWT & Session Management) owns this file.

TODO: Implement the following methods when building token rotation:
  - store(user_id, token_hash, expires_at) → RefreshToken
  - get_by_hash(token_hash) → RefreshToken | None
  - revoke(token: RefreshToken) → None
  - purge_expired() → int  (number of rows deleted)
"""
from datetime import datetime
import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models.refresh_token import RefreshToken


class TokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.is_revoked = True
        await self.db.commit()
        await self.db.refresh(token)

    async def purge_expired(self, now: datetime) -> int:
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await self.db.commit()
        return result.rowcount
