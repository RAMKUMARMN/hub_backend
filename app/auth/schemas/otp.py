"""
OTP Pydantic schemas.

Person 4 (OTP & Password Recovery) owns this file.
"""
from pydantic import BaseModel, EmailStr


class OTPRequest(BaseModel):
    """Request to send/resend an OTP to the given email."""
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    """Request to verify a 6-digit OTP."""
    email: EmailStr
    otp: str
