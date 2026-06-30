"""
Auth router — /api/v1/auth/*
"""
import random
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.device import UserDevice
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.storage_service import save_file

# Safely handle queue system import
from app.queue.producer import publish_job

# Single router instance with proper prefixing
router = APIRouter(prefix="/auth", tags=["auth"])

# --- TEMPORARY in-memory OTP store (phone -> (code, expires_at_timestamp)) ---
# NOTE: This resets on server restart. Fine for dev/testing; replace with Redis for production.
_otp_store: dict[str, tuple[str, float]] = {}
OTP_TTL_SECONDS = 300  # 5 minutes


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str


@router.post("/login/request-otp")
async def request_otp(phone: str, db: AsyncSession = Depends(get_db)):
    """
    Automated OTP Trigger.
    Looks up the user by phone number, generates an OTP, stores it, and forwards it to RabbitMQ.
    """
    # 1. Look up user by phone number
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User with this phone number not found")

    # 2. Look up the user's most recently registered device token from UserDevice table
    device_result = await db.execute(
        select(UserDevice)
        .where(UserDevice.user_id == user.id)
        .order_by(UserDevice.id.desc())
    )
    device = device_result.scalars().first()

    if not device:
        raise HTTPException(
            status_code=400,
            detail="No registered device found for this user. Please register a device first via /api/v1/devices/register."
        )

    target_device_token = device.device_token

    # 3. Generate a random 6-digit OTP code dynamically
    otp_code = str(random.randint(100000, 999999))

    # 4. Store it in memory with an expiry timestamp
    _otp_store[phone] = (otp_code, time.time() + OTP_TTL_SECONDS)

    payload = {
        "job_id": f"otp-{phone}-{otp_code}",
        "channel": "push",
        "recipient": target_device_token,
        "title": "Your Hub Verification Code",
        "body": f"Your security OTP code is {otp_code}. Do not share this with anyone.",
        "data": {"type": "otp_verification"},
        "attempt": 1,
        "max_attempts": 3
    }

    print(f"🔵 About to publish OTP job: {payload['job_id']} to {payload['recipient'][:20]}...")
    await publish_job(queue_name="push.process", payload=payload)
    print(f"🟢 Successfully published OTP job: {payload['job_id']}")

    return {"status": "success", "message": "OTP sent successfully via background worker."}


@router.post("/login/verify-otp", response_model=TokenResponse)
async def verify_otp(body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    """
    Verifies the submitted OTP code against the stored one for this phone number.
    On success, logs the user in and returns access/refresh tokens.
    """
    stored = _otp_store.get(body.phone)

    if not stored:
        raise HTTPException(status_code=400, detail="No OTP was requested for this phone number, or it has expired.")

    stored_code, expires_at = stored

    if time.time() > expires_at:
        del _otp_store[body.phone]
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if body.code != stored_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    # OTP is correct — clear it so it can't be reused
    del _otp_store[body.phone]

    # Look up the user and issue tokens (logs them in)
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        hashed_password=hash_password(body.password),
        device_tokens=[]
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if body.device_token:
        existing_device = await db.execute(
            select(UserDevice).where(UserDevice.device_token == body.device_token)
        )
        device = existing_device.scalars().first()

        if device:
            device.user_id = user.id
        else:
            device = UserDevice(
                user_id=user.id,
                device_token=body.device_token,
                platform="android",
            )
            db.add(device)

        await db.commit()

    # Send welcome email via background worker
    welcome_payload = {
        "job_id": f"welcome-{user.id}",
        "channel": "email",
        "recipient": user.email,
        "subject": "Welcome to CixioHub!",
        "body": f"Hi {user.full_name},\n\nWelcome to CixioHub! Your account has been created successfully.\n\nWe're glad to have you on board.",
        "attempt": 1,
        "max_attempts": 3
    }
    print(f"🔵 About to publish welcome email job: {welcome_payload['job_id']} to {welcome_payload['recipient']}...")
    await publish_job(queue_name="email.process", payload=welcome_payload)
    print(f"🟢 Successfully published welcome email job: {welcome_payload['job_id']}")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.phone is not None:
        current_user.phone = body.phone
    if body.device_token is not None:
        tokens = list(current_user.device_tokens or [])
        if body.device_token not in tokens:
            tokens.append(body.device_token)
        current_user.device_tokens = tokens
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    contents = await file.read()
    filename = file.filename or "avatar"
    if "." not in filename:
        ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
        ext = ext_map.get(file.content_type, "png")
        filename = f"{filename}.{ext}"
    path = await save_file(contents, filename, current_user.id)
    current_user.avatar_url = path
    await db.commit()
    await db.refresh(current_user)
    return current_user