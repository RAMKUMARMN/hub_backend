"""
OTP service — 6-digit OTP generation, storage, and verification using Redis.

Person 4 (OTP & Password Recovery) owns this file.
"""
import secrets
import uuid
from app.redis import redis_client


class OTPService:
    @staticmethod
    def generate_code() -> str:
        """Generate a cryptographically-secure 6-digit OTP string."""
        return str(secrets.randbelow(1_000_000)).zfill(6)
    @classmethod
    async def generate_otp(cls, user_id: uuid.UUID, purpose: str, expires_in_seconds: int = 600) -> str:
        """
        Generate and persist a 6-digit OTP code in Redis.
        Automatically overwrites any existing OTP code for this user/purpose.
        """
        code = cls.generate_code()
        key = f"otp:{purpose}:{str(user_id)}"
        await redis_client.set(key, code, ex=expires_in_seconds)
        return code

    @staticmethod
    async def verify_otp(user_id: uuid.UUID, code: str, purpose: str) -> bool:
        """
        Retrieve and validate the OTP code from Redis.
        If valid, the key is immediately deleted to ensure single-use verification.
        """
        key = f"otp:{purpose}:{str(user_id)}"
        stored_code = await redis_client.get(key)
        if stored_code and stored_code == code:
            await redis_client.delete(key)
            return True
        return False

    @classmethod
    async def resend_otp(cls, user_id: uuid.UUID, purpose: str, expires_in_seconds: int = 600) -> str:
        """
        Invalidate previous OTP and generate a new one.
        """
        key = f"otp:{purpose}:{str(user_id)}"
        await redis_client.delete(key)
        return await cls.generate_otp(user_id, purpose, expires_in_seconds)
