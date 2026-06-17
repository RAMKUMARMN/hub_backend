from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.google_oauth import oauth
from app.auth.services.oauth_service import OAuthService

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