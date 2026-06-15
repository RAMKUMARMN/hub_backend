"""
OTP repository — DEPRECATED in favor of Redis-based OTP storage.
Kept in place for repository mapping compatibility.

Person 4 (OTP & Password Recovery) owns this file.
"""
from sqlalchemy.ext.asyncio import AsyncSession


class OTPRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: implement OTP persistence methods
