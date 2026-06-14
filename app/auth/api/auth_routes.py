"""
Auth API routes — /api/v1/auth/*

Person 1 owns: /register, /login, /logout
Person 2 owns: /refresh
All:           /me, /profile, /avatar
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.auth.security.jwt import decode_token
from app.auth.services.auth_service import AuthService
from app.auth.services.token_service import TokenService
from app.auth.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.models.user import User
from app.services.storage_service import save_file

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Person 1 ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.

    TODO (Person 1):
      - Restrict to @tkmce.ac.in domain (utils/validators.py).
      - Trigger OTP verification email after creation (OTPService).
    """
    user = await AuthService(db).register(body)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password and receive a JWT pair.

    TODO (Person 1):
      - Check account status (pending / suspended) before issuing tokens.
    """
    user = await AuthService(db).login(body.email, body.password)
    return await TokenService.issue_pair(user, db)


@router.post("/logout")
async def logout(
    body: RefreshRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout the current user.

    For stateless JWT: client discards tokens.
    If a refresh token is provided, it is revoked in the database.
    """
    if body and body.refresh_token:
        import hashlib
        from app.auth.repositories.token_repository import TokenRepository
        token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
        repo = TokenRepository(db)
        stored_token = await repo.get_by_hash(token_hash)
        if stored_token and not stored_token.is_revoked:
            await repo.revoke(stored_token)
            
    return {"detail": "Logged out"}


# ── Person 2 ───────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange a valid refresh token for a new JWT pair.

    TODO (Person 2):
      - Validate the stored refresh token in DB (TokenRepository).
      - Revoke the old token on rotation (token rotation pattern).
    """
    from jose import JWTError
    import hashlib
    from app.auth.repositories.token_repository import TokenRepository

    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # Validate the stored refresh token in DB
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    repo = TokenRepository(db)
    stored_token = await repo.get_by_hash(token_hash)
    
    if not stored_token or stored_token.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")
        
    # Revoke the old token on rotation
    await repo.revoke(stored_token)

    from app.auth.repositories.user_repository import UserRepository
    import uuid
    user_id = payload.get("sub")
    user = await UserRepository(db).get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return await TokenService.issue_pair(user, db)


# ── Shared ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display name, phone number, or push notification token."""
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
    """Upload a profile picture (JPEG, PNG, or WebP)."""
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed",
        )

    contents = await file.read()
    path = await save_file(contents, file.filename, current_user.id)
    current_user.avatar_url = path
    await db.commit()
    await db.refresh(current_user)
    return current_user
