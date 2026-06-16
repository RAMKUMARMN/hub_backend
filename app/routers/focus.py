import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User
from app.schemas.focus import StartSessionRequest, FocusSessionResponse, ProductivityMetricsResponse
from app.services.focus_service import FocusService

router = APIRouter(prefix="/focus", tags=["focus"])

@router.post("/sessions", response_model=FocusSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_focus(
    body: StartSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FocusService(db).start_session(current_user.id, body.type)

@router.post("/sessions/{session_id}/pause", response_model=FocusSessionResponse)
async def pause_focus(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FocusService(db).pause_session(session_id, current_user.id)

@router.post("/sessions/{session_id}/resume", response_model=FocusSessionResponse)
async def resume_focus(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FocusService(db).resume_session(session_id, current_user.id)

@router.post("/sessions/{session_id}/stop", response_model=FocusSessionResponse)
async def stop_focus(
    session_id: uuid.UUID,
    status: str = "completed",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FocusService(db).stop_session(session_id, current_user.id, status)

@router.get("/metrics", response_model=ProductivityMetricsResponse)
async def get_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await FocusService(db).get_metrics(current_user.id)
