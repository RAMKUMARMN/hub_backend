"""
Auth Pydantic schemas — request/response contracts.

Shared contract agreed upon by all 4 developers:
  POST /auth/login  →  TokenResponse
  POST /auth/register  →  UserResponse
  GET  /auth/me     →  UserResponse

All developers must NOT change field names here without team agreement.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
class PhoneRequest(BaseModel):
    phone: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordConfirm(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OtpVerifyRequest(BaseModel):
    phone: str
    otp: str


class TokenResponse(BaseModel):
    """Returned by /login and /refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    """Public user representation — never include password hash here."""
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    avatar_url: str | None
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    device_token: str | None = None  # FCM/APNs push notification token


class GoogleLoginRequest(BaseModel):
    """Request body for POST /auth/google — client sends the Google ID token."""
    id_token: str

    device_token: str | None = None  # FCM/APNs push token

class LoginOtpResponse(BaseModel):
    message: str
    phone: str

class EmailRequest(BaseModel):
    email: EmailStr

class EmailOtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
