from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User

from app.auth.security.dependencies import get_current_user

from app.schemas.preferences import (
    PreferencesResponse,
    PreferencesUpdate,
    SecuritySettingsUpdate,
)

from app.services.preferences_service import PreferencesService

router = APIRouter(
    prefix="/preferences",
    tags=["preferences"],
)


@router.get(
    "/",
    response_model=PreferencesResponse,
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's preferences.
    Creates default preferences if none exist.
    """

    return await PreferencesService(
        db
    ).get_or_create_preferences(current_user)


@router.put(
    "/",
    response_model=PreferencesResponse,
)
async def update_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update theme and notification settings.
    """

    return await PreferencesService(
        db
    ).update_preferences(
        user=current_user,
        theme=body.theme,
        notification_settings=body.notification_settings,
    )


@router.get("/security")
async def get_security_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get security preferences.
    """

    preferences = await PreferencesService(
        db
    ).get_or_create_preferences(current_user)

    return preferences.security_settings


@router.put(
    "/security",
    response_model=PreferencesResponse,
)
async def update_security_settings(
    body: SecuritySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update security settings.
    """

    return await PreferencesService(
        db
    ).update_security(
        user=current_user,
        security_settings=body.security_settings,
    )