from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.services.oauth_service import OAuthService

router = APIRouter(
    prefix="/auth",
    tags=["oauth"]
)


@router.get("/google")
async def google_login():

    return {
        "message": "Google OAuth login endpoint"
    }


@router.get("/google/callback")
async def google_callback(
    db: AsyncSession = Depends(get_db)
):

    mock_google_user = {
        "email": "student@tkmce.ac.in",
        "full_name": "TKM Student"
    }

    return await OAuthService(db).handle_google_user(
        email=mock_google_user["email"],
        full_name=mock_google_user["full_name"]
    )