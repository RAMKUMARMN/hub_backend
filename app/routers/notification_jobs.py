"""Notification jobs router — /api/v1/notification-jobs/*"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification_job import NotificationJob
from app.schemas.notification_job import (
    CreateNotificationJobRequest,
    NotificationJobResponse,
)

router = APIRouter(prefix="/notification-jobs", tags=["notification-jobs"])


@router.post("/", response_model=NotificationJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(body: CreateNotificationJobRequest, db: AsyncSession = Depends(get_db)):
    job = NotificationJob(channel=body.channel, total=body.total)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{job_id}", response_model=NotificationJobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationJob).where(NotificationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/", response_model=list[NotificationJobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationJob).order_by(NotificationJob.created_at.desc()))
    return result.scalars().all()