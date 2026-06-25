"""
Auth router — /api/v1/auth/*

Students: implement each TODO endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select,or_
from sqlalchemy.ext.asyncio import AsyncSession
import random
import httpx

# These are the imports that were likely lost
from app.database import get_db 
from app.db.redis import redis_client

import httpx
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    EmailRequest,
    LoginOtpResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    ForgotPasswordRequest,
    ResetPasswordConfirm,
    UserResponse,
    PhoneRequest,
    OtpVerifyRequest,
    EmailOtpVerifyRequest
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.storage_service import save_file

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account with duplicate email and phone checks.
    """
    # Use .limit(1) and .scalar() to avoid MultipleResultsFound error
    existing_user = await db.execute(
        select(User).where(
            or_(
                User.email == body.email,
                (User.phone == body.phone) if body.phone else False
            )
        ).limit(1)
    )
    
    if existing_user.scalar():
        raise HTTPException(
            status_code=400, 
            detail="Email or phone number already registered"
        )

    # Create user
    user = User(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Notify service logic
    try:
        async with httpx.AsyncClient(base_url=settings.notify_service_url, timeout=30) as client:
            await client.post(
                "/api/v1/notify/send",
                json={
                    "channel": "email",
                    "recipient": user.email,
                    "subject": "Welcome to CixioHub",
                    "body": f"Hello {user.full_name}, welcome to CixioHub!",
                },
            )
    except Exception:
        pass

    # Generate tokens for the new user
    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer"
    }
@router.post("/login", response_model=LoginOtpResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate and return JWT tokens.

    TODO:
      1. Look up user by email.
      2. Verify password with verify_password().
      3. Return access + refresh tokens.
    """
    # 1. Debug: Print incoming body
    print(f"DEBUG: Attempting login for email: {body.email}")
    
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    # 2. Debug: Check if user was found
    if not user:
        print(f"DEBUG: User not found in database for email: {body.email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # 3. Debug: Verify password with print statements
    is_valid = verify_password(body.password, user.hashed_password)
    print(f"DEBUG: Password verification result: {is_valid}")
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate OTP and store in Redis (expires in 5 minutes)
    otp = str(random.randint(100000, 999999))
    print(f"DEBUG: The OTP for {user.phone} is {otp}")
    redis_client.setex(f"otp:{user.phone}", 300, otp)

    # Trigger Notify service
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://localhost:8001/api/v1/notify/send",
                json={
                    "channel": "sms",
                    "recipient": user.phone,
                    "body": f"Your verification code is {otp}"
                }
            )
        except Exception as e:
            print(f"DEBUG: Notify service failed: {e}")

    # Return structure needs to match what your frontend expects.
    # Note: If your frontend expects TokenResponse, you may need 
    # to handle the OTP state before issuing tokens.
    return {"message": "OTP sent to your phone", "phone": user.phone}
@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(body: OtpVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP and return JWT tokens."""
    phone = body.phone
    otp = body.otp
    
    # Fetch from Redis
    stored_otp_data = redis_client.get(f"otp:{phone}")
    
    # 1. Handle both bytes and string responses from Redis
    if isinstance(stored_otp_data, bytes):
        stored_otp = stored_otp_data.decode('utf-8')
    else:
        stored_otp = stored_otp_data
    
    print(f"DEBUG: Verifying OTP. Received: {otp}, Stored: {stored_otp}")

    # 2. Compare values
    if not stored_otp or stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # 3. Clean up and return tokens
    redis_client.delete(f"otp:{phone}")
    
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
@router.post("/verify-phoneno-and-register")
async def verify_phoneno_and_register(
    body: OtpVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    phone = body.phone
    otp = body.otp
    
    stored_otp = redis_client.get(f"otp:{phone}")
    
    if not stored_otp or stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    redis_client.delete(f"otp:{phone}")
    
    return {"message": "OTP verified. You can now proceed to registration."}

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

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    # 1. Look up user
    result = await db.execute(select(User).where(User.email == body.email).limit(1))
    user = result.scalar()
    
    # Security note: Always return success to prevent email enumeration attacks
    if not user:
        return {"message": "If this email is registered, a code has been sent."}

    # 2. Generate and store code
    reset_code = str(random.randint(100000, 999999))
    print(f"\n>>> DEBUG: Reset code for {user.email} is: {reset_code} <<<\n")
    redis_client.setex(f"reset:{user.email}", 600, reset_code)

    # 3. Notify with error handling
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "http://localhost:8001/api/v1/notify/send",
                json={
                    "channel": "sms",
                    "recipient": user.phone,
                    "body": f"Your password reset code is {reset_code}"
                }
            )
    except (httpx.ConnectError, httpx.RequestError) as e:
        # Log the failure but do not crash the user's request
        print(f"CRITICAL: Notify service unreachable: {e}")
        # Optional: You might want to raise an HTTPException(503) here 
        # if the notification is mandatory for your business process.
        raise HTTPException(
            status_code=503, 
            detail="We are having trouble sending your reset code. Please try again later."
        )

    return {"message": "Reset code sent"}
@router.post("/reset-password")
async def reset_password(body: ResetPasswordConfirm, db: AsyncSession = Depends(get_db)):
    stored_code = redis_client.get(f"reset:{body.email}")
    
    if not stored_code or stored_code != body.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    user.hashed_password = hash_password(body.new_password)
    
    await db.commit()
    redis_client.delete(f"reset:{body.email}")
    
    return {"message": "Password updated successfully"}

@router.post("/phone_number_verification")
async def phone_number_verification(request: PhoneRequest):
    phone = request.phone
    if not phone or phone.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Phone number is required to send an OTP."
        )

    otp = str(random.randint(100000, 999999))
    redis_client.setex(f"otp:{phone}", 300, otp)
    print(f"\n>>> DEBUG: Verification OTP for {phone} is: {otp} <<<\n")
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://localhost:8001/api/v1/notify/send",
                json={
                    "channel": "sms",
                    "recipient": phone,
                    "body": f"Your registration code is {otp}"
                }
            )
        except httpx.ConnectError:
            print("Notify service down, skipping SMS.")
            
    return {"message": "OTP sent successfully"}

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
    path = await save_file(contents, file.filename, current_user.id)
    current_user.avatar_url = path
    await db.commit()
    await db.refresh(current_user)
    return current_user
import os
from pathlib import Path
from fastapi import Response

@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.avatar_url:
        raise HTTPException(status_code=404, detail="Avatar not found")

    # Clean the string from the DB
    path_from_db = user.avatar_url.replace("\\", "/")
    
    # Check if the path is ALREADY absolute (starts with C:/)
    if ":" in path_from_db:
        full_path = Path(path_from_db)
    else:
        # Otherwise, treat it as relative to your project
        base_dir = Path(__file__).resolve().parent.parent.parent
        # If it doesn't already start with 'uploads', add it
        if not path_from_db.startswith("uploads/"):
            full_path = base_dir / "uploads" / path_from_db
        else:
            full_path = base_dir / path_from_db

    print(f"DEBUG: FINAL LOOKUP PATH: {full_path}")
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {full_path}")
        
    return FileResponse(full_path)

@router.post("/verify-email-otp")
async def verify_email_otp(body: EmailOtpVerifyRequest): 
    email = body.email 
    otp = body.otp
    
    # Fetch from Redis
    stored_otp_data = redis_client.get(f"otp_email:{email}")
    
    if not stored_otp_data:
        raise HTTPException(status_code=400, detail="OTP expired or not requested")
        
    # --- FIX STARTS HERE ---
    # If it's bytes, decode it. If it's already a string, use it as is.
    if isinstance(stored_otp_data, bytes):
        stored_otp = stored_otp_data.decode('utf-8')
    else:
        stored_otp = str(stored_otp_data) 
    # --- FIX ENDS HERE ---
    
    if stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Clean up
    redis_client.delete(f"otp_email:{email}")
    
    return {"message": "Email verified successfully"}
    
    return {"message": "Email verified successfully"}
@router.post("/email_verification")
async def email_verification(body: EmailRequest):
    """
    Generates and sends an OTP to the user's email.
    Assumes EmailOtpVerifyRequest contains the email field.
    """
    print(f"DEBUG: Received request body: {body}")
    email = body.email
    
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="A valid email is required to send an OTP."
        )

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store in Redis with a 5-minute (300s) expiry
    # Note: Using 'otp_email:' prefix to match your verify-email-otp endpoint
    redis_client.setex(f"otp_email:{email}", 300, otp)
    
    print(f"\n>>> DEBUG: Email Verification OTP for {email} is: {otp} <<<\n")
    
    # Trigger Notify service
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://localhost:8001/api/v1/notify/send",
                json={
                    "channel": "email",
                    "recipient": email,
                    "subject": "CixioHub Verification Code",
                    "body": f"Your verification code is {otp}"
                }
            )
        except Exception as e:
            print(f"DEBUG: Notify service failed to send email: {e}")
            # You might want to raise an error if email is mandatory
            
    return {"message": "OTP sent to your email"}