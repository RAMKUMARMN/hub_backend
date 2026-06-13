"""
Token repository — stores and validates refresh tokens in the database.

Person 2 (JWT & Session Management) owns this file.

TODO: Implement the following methods when building token rotation:
  - store(user_id, token_hash, expires_at) → RefreshToken
  - get_by_hash(token_hash) → RefreshToken | None
  - revoke(token: RefreshToken) → None
  - purge_expired() → int  (number of rows deleted)
"""
from sqlalchemy.ext.asyncio import AsyncSession


class TokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: implement token rotation methods
