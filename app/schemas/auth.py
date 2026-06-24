import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
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
    device_token: str | None = None  # FCM/APNs push token


class GoogleLoginRequest(BaseModel):
    id_token: str

