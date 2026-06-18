from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_preferences import UserPreferences


class PreferencesService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_preferences(
        self,
        user: User,
    ) -> UserPreferences:

        result = await self.db.execute(
            select(UserPreferences).where(
                UserPreferences.user_id == user.id
            )
        )

        preferences = result.scalar_one_or_none()

        if preferences:
            return preferences

        preferences = UserPreferences(
            user_id=user.id,
            theme="light",
            notification_settings={
                "email": True,
                "push": True,
            },
            security_settings={
                "two_factor": False,
            },
        )

        self.db.add(preferences)

        await self.db.commit()
        await self.db.refresh(preferences)

        return preferences

    async def update_preferences(
        self,
        user: User,
        theme: str | None,
        notification_settings: dict | None,
    ) -> UserPreferences:

        preferences = await self.get_or_create_preferences(user)

        if theme is not None:
            preferences.theme = theme

        if notification_settings is not None:
            preferences.notification_settings = notification_settings

        await self.db.commit()
        await self.db.refresh(preferences)

        return preferences

    async def update_security(
        self,
        user: User,
        security_settings: dict,
    ) -> UserPreferences:

        preferences = await self.get_or_create_preferences(user)

        preferences.security_settings = security_settings

        await self.db.commit()
        await self.db.refresh(preferences)

        return preferences