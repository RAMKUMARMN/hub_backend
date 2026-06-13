"""
OTP repository — stores and validates OTP codes.

Person 4 (OTP & Password Recovery) owns this file.

TODO: Implement the following methods:
  - create(user_id, code, purpose, expires_at) → OTPCode
  - get_valid(user_id, code, purpose) → OTPCode | None  (not expired, not used)
  - mark_used(otp: OTPCode) → None
  - purge_expired() → int
"""
from sqlalchemy.ext.asyncio import AsyncSession


class OTPRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # TODO: implement OTP persistence methods
