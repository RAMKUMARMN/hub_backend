from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def create_audit_log(
    db: AsyncSession,
    user_id,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: str | None = None,
):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )

    db.add(audit)
    await db.commit()