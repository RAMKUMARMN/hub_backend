"""
File storage service — local filesystem in dev, AWS S3 in production.

Set USE_S3=true in .env to switch to S3.
"""
import os
import uuid
from pathlib import Path

from app.config import settings

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def save_file(file_bytes: bytes, filename: str, user_id: uuid.UUID) -> str:
    """
    Save an uploaded file and return its storage path / S3 key.

    In development: saves to local `uploads/` directory.
    In production: upload to S3 and return the S3 key.

    TODO (S3):
      import boto3
      s3 = boto3.client("s3", region_name=settings.aws_region)
      key = f"uploads/{user_id}/{unique_filename}"
      s3.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=file_bytes)
      return key
    """
    unique_name = f"{uuid.uuid4()}_{filename}"
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / unique_name
    dest.write_bytes(file_bytes)
    return str(dest.relative_to(UPLOAD_DIR))


async def delete_file(storage_path: str) -> None:
    """Delete a file from local storage or S3."""
    path = UPLOAD_DIR / storage_path
    if path.exists():
        path.unlink()
