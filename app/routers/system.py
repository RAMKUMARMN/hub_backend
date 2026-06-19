from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from app.models.audit_log import AuditLog
from app.models.system_settings import SystemSettings
from app.models.user import User

from app.auth.security.dependencies import get_current_user

from app.schemas.system import (
    HealthResponse,
    SystemSettingUpdate,
)

from app.services.system_service import SystemService

router = APIRouter(
    prefix="/system",
    tags=["system"],
)

@router.get(
    "/health",
    response_model=HealthResponse,
)
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    """
    Health check endpoint.
    """

    return await SystemService(
        db
    ).health_check()
    
@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin-only audit log viewer.
    """

    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )

    return result.scalars().all()

@router.get("/settings")
async def get_system_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all system settings.
    Admin only.
    """

    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    result = await db.execute(
        select(SystemSettings)
    )

    return result.scalars().all()

@router.put("/settings/{key}")
async def update_system_setting(
    key: str,
    body: SystemSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create/update a system setting.
    Admin only.
    """

    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    result = await db.execute(
        select(SystemSettings).where(
            SystemSettings.key == key
        )
    )

    setting = result.scalar_one_or_none()

    if setting is None:
        setting = SystemSettings(
            key=key,
            value=body.value,
        )

        db.add(setting)

    else:
        setting.value = body.value

    await db.commit()
    await db.refresh(setting)

    return setting