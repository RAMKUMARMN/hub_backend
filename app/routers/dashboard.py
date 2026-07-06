from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.services.dashboard_service import DashboardService
from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service(db=Depends(get_db)):
    return DashboardService(db)


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return await service.get_dashboard(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}")
async def get_dashboard(
    user_id: UUID,
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return await service.get_dashboard(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))