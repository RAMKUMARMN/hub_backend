import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.google_oauth import oauth
from app.auth.security.jwt import (
    create_access_token,
    create_refresh_token,
    verify_google_token,
)
from app.auth.services.oauth_service import OAuthService
from app.auth.schemas.auth import GoogleLoginRequest, TokenResponse
from app.auth.services.auth_service import hash_password
from app.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["oauth"]
)


@router.get("/google")
async def google_login(request: Request):

    redirect_uri = request.url_for("google_callback")

    print("REDIRECT URI =", redirect_uri)
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    token = await oauth.google.authorize_access_token(request)

    user_info = token.get("userinfo")

    if not user_info:
        user_info = await oauth.google.userinfo(token=token)

    email = user_info["email"]
    full_name = user_info["name"]

    return await OAuthService(db).handle_google_user(
        email=email,
        full_name=full_name,
    )


@router.post("/google", response_model=TokenResponse)
async def google_token_login(
    body: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate a user via a Google ID token (for mobile/SPA clients).

    The client (Flutter/Next.js) handles the Google login prompt,
    obtains an id_token, and POSTs it here.
    We verify it with Google, then return our own JWT tokens.
    """
    payload = await verify_google_token(body.id_token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid Google token")

    email = payload.get("email")
    full_name = payload.get("name", "Google User")
    picture = payload.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # First-time Google user — register them automatically
        random_pass = secrets.token_urlsafe(32)
        is_active = True
        status_val = "active" if email.endswith("@tkmce.ac.in") else "pending"
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(random_pass),
            avatar_url=picture,
            is_active=is_active,
            status=status_val,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif picture and not user.avatar_url:
        # Update avatar from Google if they don't have one yet
        user.avatar_url = picture
        await db.commit()
        await db.refresh(user)

    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
        )
    elif user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
        )

    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


from pydantic import BaseModel, EmailStr

class GoogleLoginMobileRequest(BaseModel):
    email: EmailStr
    name: str
    google_id: str

@router.post("/google-login")
async def google_login_mobile(
    body: GoogleLoginMobileRequest,
    db: AsyncSession = Depends(get_db)
):
    from app.auth.repositories.user_repository import UserRepository
    from app.auth.services.token_service import TokenService
    from fastapi import HTTPException, status
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(body.email)
    
    if not user:
        is_active = True
        status_val = "active" if body.email.endswith("@tkmce.ac.in") else "pending"
        user = await user_repo.create(
            email=body.email,
            full_name=body.name,
            hashed_password=hash_password("oauth-user"),
            phone=None,
            is_active=is_active,
            status=status_val,
        )
        
    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
        )
    elif user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
        )
        
    tokens = await TokenService.issue_pair(user, db)
    
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "user": {
            "id": str(user.id),
            "name": user.full_name,
            "email": user.email,
        }
    }
