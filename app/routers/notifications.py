import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import NotificationJob
from app.models.user import User
from app.schemas.notification import NotificationJobResponse

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"]
)


@router.get("/jobs", response_model=list[NotificationJobResponse])
async def list_notification_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationJob)
        .where(NotificationJob.user_id == current_user.id)
        .order_by(NotificationJob.created_at.desc())
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=NotificationJobResponse)
async def get_notification_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationJob).where(
            NotificationJob.id == job_id,
            NotificationJob.user_id == current_user.id,
        )
    )

    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Notification job not found"
        )

    return job