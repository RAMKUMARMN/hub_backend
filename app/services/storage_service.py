"""
File storage service — local filesystem in dev (or when Cloudinary credentials are missing),
and Cloudinary when configured.
"""
import io
import uuid
import logging
from pathlib import Path

import cloudinary
import cloudinary.uploader

from app.config import settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Determine if Cloudinary is configured
use_cloudinary = bool(
    settings.cloudinary_cloud_name and
    settings.cloudinary_api_key and
    settings.cloudinary_api_secret
)

if use_cloudinary:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    logger.info("Cloudinary storage service configured successfully.")
else:
    logger.info("Cloudinary credentials not set. Falling back to local filesystem storage.")


async def save_file(
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID,
) -> str:
    """
    Save an uploaded file and return its storage path.
    Uploads to Cloudinary if configured; otherwise saves to local `uploads/` directory.
    """
    if use_cloudinary:
        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(file_bytes),
                resource_type="auto",
                folder=f"uploads/{user_id}",
                public_id=f"{uuid.uuid4()}_{filename.rsplit('.', 1)[0]}",
                overwrite=False,
            )
            return result["secure_url"]
        except Exception as exc:
            logger.error("Failed to upload to Cloudinary: %s. Falling back to local storage.", exc)

    # Local fallback
    unique_name = f"{uuid.uuid4()}_{filename}"
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / unique_name
    dest.write_bytes(file_bytes)
    return str(dest.relative_to(UPLOAD_DIR))


async def delete_file(storage_path: str) -> None:
    """
    Delete a file from Cloudinary (if storage_path is a Cloudinary URL) or local filesystem.
    """
    if not storage_path:
        return

    # Check if the storage path is a Cloudinary URL
    if "/upload/" in storage_path and use_cloudinary:
        try:
            parts = storage_path.split("/upload/")
            if len(parts) != 2:
                return

            public_part = parts[1]
            if public_part.startswith("v"):
                public_part = public_part.split("/", 1)[1]

            public_id = public_part.rsplit(".", 1)[0]

            cloudinary.uploader.destroy(
                public_id,
                resource_type="auto"
            )
            return
        except Exception as exc:
            logger.warning(
                "Failed to delete Cloudinary asset: %s",
                exc
            )
            return

    # Local file deletion fallback
    try:
        path = UPLOAD_DIR / storage_path
        if path.exists() and path.is_file():
            path.unlink()
    except Exception as exc:
        logger.warning("Failed to delete local file %s: %s", storage_path, exc)
