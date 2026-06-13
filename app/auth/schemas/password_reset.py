"""
Password reset Pydantic schemas.

Person 4 (OTP & Password Recovery) owns this file.
"""
from pydantic import BaseModel, EmailStr


class PasswordResetRequest(BaseModel):
    """Request to send a password-reset email."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm a password reset using the token from the email."""
    token: str
    new_password: str
