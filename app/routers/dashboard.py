from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.services.dashboard_service import DashboardService
from app.database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service(db=Depends(get_db)):
    return DashboardService(db)


@router.get("/{user_id}")
async def get_dashboard(
    user_id: UUID,
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return await service.get_dashboard(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))