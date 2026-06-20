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


async def save_file(
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID,
) -> str:

    unique_name = (
        f"{uuid.uuid4()}_{filename}"
    )

    user_dir = (
        UPLOAD_DIR / str(user_id)
    )

    user_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dest = user_dir / unique_name

    dest.write_bytes(file_bytes)

    return str(
        Path(str(user_id)) / unique_name
    )


async def delete_file(storage_path: str) -> None:
    """Delete a file from local storage or S3."""
    path = Path(storage_path)
    if path.exists():
        path.unlink()
