"""
Admin router — /api/v1/admin/*

Requires is_admin=True on the authenticated user.
"""
import csv
import io
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_admin
from app.models.user import User
from app.auth.schemas.auth import UserResponse
from app.auth.security.password import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/users/bulk", status_code=status.HTTP_202_ACCEPTED)
async def bulk_create_users(
    file: UploadFile,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a CSV with columns: email, full_name, phone (optional).
    Creates user accounts and queues credential emails/SMS.

    TODO:
      1. Parse CSV rows.
      2. For each row, generate a temp password, hash it, create User.
      3. Publish a notification task to RabbitMQ to send credentials.
      4. Return job summary.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    contents = await file.read()
    reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))

    required_columns = {"email", "full_name"}
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")
    if not required_columns.issubset(set(rows[0].keys())):
        raise HTTPException(status_code=400, detail=f"CSV must have columns: {required_columns}")

    created = 0
    skipped = 0
    for row in rows:
        email = row["email"].strip().lower()
        full_name = row["full_name"].strip()
        phone = row.get("phone", "").strip() or None

        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        temp_password = _generate_temp_password()
        user = User(
            email=email,
            full_name=full_name,
            phone=phone,
            hashed_password=hash_password(temp_password),
        )
        db.add(user)
        created += 1
        # TODO: publish to RabbitMQ queue to send credential email/SMS

    await db.commit()
    return {"created": created, "skipped": skipped, "total": len(rows)}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
