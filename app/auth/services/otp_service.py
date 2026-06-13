"""
OTP service — 6-digit OTP generation, storage, and verification.

Person 4 (OTP & Password Recovery) owns this file.
Depends on: repositories/otp_repository.py, utils/email.py

TODO:
  1. generate_otp(user_id, purpose) → str
       - Generate a 6-digit code (secrets.randbelow).
       - Store in Redis with TTL (or use OTPRepository for DB storage).
       - Send via email using utils/email.py.

  2. verify_otp(user_id, code, purpose) → bool
       - Look up the stored OTP.
       - Check expiry and match.
       - Mark as used / delete from Redis.

  3. resend_otp(user_id, purpose) → None
       - Invalidate existing OTP, generate a new one.
"""
import secrets


def generate_otp() -> str:
    """Generate a cryptographically-secure 6-digit OTP string."""
    return str(secrets.randbelow(1_000_000)).zfill(6)
