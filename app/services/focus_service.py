import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.focus import FocusSession
from app.queue.producer import publish_focus_completed
from app.services.dashboard_service import invalidate_dashboard_cache

class FocusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_session(self, user_id: uuid.UUID, session_type: str) -> FocusSession:
        # Check if there are active/paused sessions
        active_result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.user_id == user_id,
                FocusSession.status.in_(["started", "paused"])
            )
        )
        active_session = active_result.scalars().first()
        if active_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an active focus session"
            )

        session = FocusSession(user_id=user_id, type=session_type, status="started")
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def pause_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> FocusSession:
        session = await self._get_active_session(session_id, user_id)
        if session.status != "started":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only started sessions can be paused"
            )
        session.status = "paused"
        session.paused_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def resume_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> FocusSession:
        session = await self._get_active_session(session_id, user_id)
        if session.status != "paused":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only paused sessions can be resumed"
            )
        
        paused_seconds = int((datetime.now(timezone.utc) - session.paused_at).total_seconds())
        session.total_paused_seconds += paused_seconds
        session.status = "started"
        session.paused_at = None
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def stop_session(self, session_id: uuid.UUID, user_id: uuid.UUID, finish_status: str) -> FocusSession:
        if finish_status not in ["completed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid finish status"
            )

        session = await self._get_active_session(session_id, user_id)
        end_time = datetime.now(timezone.utc)
        
        # Accumulate last paused duration if stopped while paused
        paused_seconds = session.total_paused_seconds
        if session.status == "paused" and session.paused_at:
            paused_seconds += int((end_time - session.paused_at).total_seconds())

        total_duration = (end_time - session.start_time).total_seconds() - paused_seconds
        duration_minutes = max(0, int(round(total_duration / 60.0)))

        session.status = finish_status
        session.end_time = end_time
        session.duration_minutes = duration_minutes
        await self.db.commit()
        await self.db.refresh(session)

        # Publish achievement event if focus completed successfully
        if finish_status == "completed" and session.type == "focus":
            
            await invalidate_dashboard_cache(user_id)
            
            try:
                await publish_focus_completed({
                    "user_id": str(user_id),
                    "session_id": str(session.id),
                    "duration_minutes": duration_minutes,
                    "timestamp": end_time.isoformat()
                })
            except Exception:
                # Log RabbitMQ error but do not fail the HTTP response
                pass

        return session

    async def get_metrics(self, user_id: uuid.UUID) -> dict:
        # Sum focus minutes
        focus_result = await self.db.execute(
            select(func.sum(FocusSession.duration_minutes)).where(
                FocusSession.user_id == user_id,
                FocusSession.type == "focus",
                FocusSession.status == "completed"
            )
        )
        total_focus = focus_result.scalar() or 0

        # Sum break minutes (short_break and long_break)
        break_result = await self.db.execute(
            select(func.sum(FocusSession.duration_minutes)).where(
                FocusSession.user_id == user_id,
                FocusSession.type.in_(["short_break", "long_break"]),
                FocusSession.status == "completed"
            )
        )
        total_break = break_result.scalar() or 0

        # Calculate ratio
        ratio = float(total_focus) / float(total_break) if total_break > 0 else float(total_focus)

        # Calculate productivity score: 0 to 100 scale
        # Ideally, a balanced Pomodoro ratio (e.g. 4 focus sessions of 25m = 100m to 15m short break + 20m long break = 35m breaks, approx 3:1 ratio).
        # Let's define: score = min(100, int((total_focus / (total_focus + total_break)) * 100)) if focus > 0 else 0
        total_time = total_focus + total_break
        score = min(100, int((total_focus / total_time) * 100)) if total_time > 0 else 0

        return {
            "total_focus_minutes": total_focus,
            "total_break_minutes": total_break,
            "focus_to_break_ratio": ratio,
            "productivity_score": score
        }

    async def _get_active_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> FocusSession:
        result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.id == session_id,
                FocusSession.user_id == user_id,
                FocusSession.status.in_(["started", "paused"])
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active focus session not found"
            )
        return session
