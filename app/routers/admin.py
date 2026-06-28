"""
Admin router — /api/v1/admin/*

Requires is_admin=True on the authenticated user.

"""



import csv
import httpx
import io
import secrets
import string
import uuid

from fastapi import BackgroundTasks
from app.database import AsyncSessionLocal
from app.queue.producer import (
    publish_user_cleanup,
)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repositories import UserRepository
from app.database import get_db
from app.auth.security.dependencies import get_current_admin
from app.models.user import User
from app.auth.schemas.auth import UserResponse
from app.auth.security.password import hash_password

from datetime import UTC, datetime

from app.services.dashboard_service import invalidate_dashboard_cache

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserUpdateRequest(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    status: str | None = None


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

async def _process_bulk_users(rows: list[dict]):
    async with AsyncSessionLocal() as db:
        recipients = []
        for row in rows:
            email = row["email"].strip().lower()
            full_name = row["full_name"].strip()
            phone = row.get("phone", "").strip() or None

            existing = await db.execute(
                select(User).where(User.email == email)
            )

            if existing.scalar_one_or_none():
                continue

            temp_password = _generate_temp_password()

            user = User(
                email=email,
                full_name=full_name,
                phone=phone,
                hashed_password=hash_password(temp_password),
            )

            db.add(user)
            await db.flush()

            recipients.append({
                "recipient": email,
                "subject": "Your CixioHub Credentials",
                "body": f"Hello {full_name},\n\nYour account has been created on CixioHub.\nEmail: {email}\nTemporary Password: {temp_password}\n\nPlease log in and change your password.",
                "html_body": f"<p>Hello {full_name},</p><p>Your account has been created on CixioHub.<br><strong>Email:</strong> {email}<br><strong>Temporary Password:</strong> {temp_password}</p><p>Please log in and change your password.</p>",
                "message_type": "general",
                "priority": "high",
            })

        await db.commit()

        if recipients:
            try:
                from app.config import settings
                from app.auth.security.jwt import create_access_token
                
                token = create_access_token({"sub": "admin", "role": "admin"})
                headers = {"Authorization": f"Bearer {token}"}
                payload = {
                    "channel": "email",
                    "recipients": recipients
                }
                # Replace /send with /bulk
                bulk_url = settings.notification_service_url.replace("/send", "/bulk")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(bulk_url, json=payload, headers=headers)
                    response.raise_for_status()
            except Exception as e:
                print("Failed to send bulk credentials notification:", e)


@router.post("/users/bulk", status_code=status.HTTP_202_ACCEPTED)
async def bulk_create_users(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_admin: dict = Depends(get_current_admin),
    
):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    contents = await file.read()
    reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))

    required_columns = {"email", "full_name"}
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")

    if not required_columns.issubset(set(rows[0].keys())):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have columns: {required_columns}"
        )

    job_id = str(uuid.uuid4())
    
    background_tasks.add_task(
        _process_bulk_users,
        rows
    )

    return {
        "job_id": job_id,
        "status": "processing"
    }


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()

@router.get("/pending-users")
async def pending_users(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    return await UserRepository(db).get_pending_users()

@router.patch("/approve/{user_id}")
async def approve_user(
    user_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    user = await UserRepository(db).approve_user(user_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "message": "User approved successfully",
        "user_id": str(user.id)
    }


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    current_admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.status is not None:
        user.status = body.status

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.deleted_at = datetime.now(UTC)
    await db.commit()
    await invalidate_dashboard_cache(str(user.id))
    await publish_user_cleanup(str(user.id))