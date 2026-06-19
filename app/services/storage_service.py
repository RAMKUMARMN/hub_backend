"""
File storage service — local filesystem in dev, AWS S3 in production.

Set USE_S3=true in .env to switch to S3.

    
    Save an uploaded file and return its storage path / S3 key.

    In development: saves to local `uploads/` directory.
    In production: upload to S3 and return the S3 key.

        File storage service using Cloudinary.
        save_file() uploads files to Cloudinary and returns the secure URL.
        delete_file() removes Cloudinary assets.

    TODO (S3):
      import boto3
      s3 = boto3.client("s3", region_name=settings.aws_region)
      key = f"uploads/{user_id}/{unique_filename}"
      s3.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=file_bytes)
      return key
    
    
"""
import io
import uuid
import logging

import cloudinary
import cloudinary.uploader


from app.config import settings

logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


async def save_file(
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID,
) -> str:
    """
    Upload file to Cloudinary and return secure URL.
    """

    result = cloudinary.uploader.upload(
        io.BytesIO(file_bytes),
        resource_type="auto",
        folder=f"uploads/{user_id}",
        public_id=f"{uuid.uuid4()}_{filename.rsplit('.', 1)[0]}",
        
        overwrite=False,
    )

    return result["secure_url"]


async def delete_file(storage_path: str) -> None:
    """
    Delete Cloudinary asset using URL stored in database.
    """

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

    except Exception as exc:
        logger.warning(
            "Failed to delete Cloudinary asset: %s",
            exc
        )
