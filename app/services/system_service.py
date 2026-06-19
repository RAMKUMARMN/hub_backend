from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.system_settings import SystemSettings


class SystemService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        user_id,
        action: str,
        resource: str,
        metadata: dict | None = None,
    ):
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            metadata=metadata or {},
        )

        self.db.add(log)

        await self.db.commit()
        await self.db.refresh(log)

        return log

    async def health_check(self):

        health = {
            "database": "down",
            "redis": "unknown",
            "rabbitmq": "unknown",
            "qdrant": "unknown",
        }

        try:
            await self.db.execute(text("SELECT 1"))
            health["database"] = "up"
        except Exception:
            pass

        return health

    async def get_audit_logs(
        self,
        limit: int = 50,
    ):
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )

        return result.scalars().all()

    async def get_system_settings(self):

        result = await self.db.execute(
            select(SystemSettings)
        )

        return result.scalars().all()

    async def update_system_setting(
        self,
        key: str,
        value: dict,
    ):

        result = await self.db.execute(
            select(SystemSettings).where(
                SystemSettings.key == key
            )
        )

        setting = result.scalar_one_or_none()

        if not setting:
            setting = SystemSettings(
                key=key,
                value=value,
            )

            self.db.add(setting)

        else:
            setting.value = value

        await self.db.commit()
        await self.db.refresh(setting)

        return setting