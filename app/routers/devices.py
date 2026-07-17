from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.device import UserDevice
from app.models.user import User
from app.schemas.device import DeviceRegisterSchema

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", status_code=status.HTTP_200_OK)
async def register_or_update_device(
    payload: DeviceRegisterSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if this device token already exists in the database
    result = await db.execute(
        select(UserDevice).where(UserDevice.device_token == payload.device_token)
    )
    existing_device = result.scalar_one_or_none()

    if existing_device:
        # Update the owner to the current logged-in user
        existing_device.user_id = current_user.id
        existing_device.platform = payload.platform
        await db.commit()
        return {"status": "updated", "message": "Device token updated for current user."}

    # Otherwise, register it as a completely new device
    new_device = UserDevice(
        user_id=current_user.id,
        device_token=payload.device_token,
        platform=payload.platform,
    )
    
    # Add to the async session track and commit safely
    db.add(new_device)
    await db.commit()
    
    return {"status": "registered", "message": "New device token saved successfully."}