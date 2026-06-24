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
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(random_pass),
            avatar_url=picture,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif picture and not user.avatar_url:
        # Update avatar from Google if they don't have one yet
        user.avatar_url = picture
        await db.commit()
        await db.refresh(user)

    token_data = {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )