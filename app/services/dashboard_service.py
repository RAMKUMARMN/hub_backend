import uuid
import json
from datetime import datetime, timedelta
from asyncio import gather


from sqlalchemy import select, func
from sqlalchemy import select, func, case
from app.redis import redis_client

from app.models.todo import Todo
from app.models.focus import FocusSession
from app.models.calendar import CalendarEvent as Event
from app.models.focus import Achievement


async def invalidate_dashboard_cache(user_id: uuid.UUID):
    keys = await redis_client.keys(f"dashboard:{user_id}:*")

    if keys:
        await redis_client.delete(*keys)


class DashboardService:
    def __init__(self, db):
        self.db = db

    async def get_dashboard(self, user_id: uuid.UUID):
        iso_week = datetime.utcnow().isocalendar()[1]
        cache_key = f"dashboard:{user_id}:{iso_week}"

        cached = await redis_client.get(cache_key)
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return json.loads(cached)

        (
            todos,
            focus,
            calendar,
            achievements,
            weekly_stats,
        ) = await gather(
            self._get_todo_stats(user_id),
            self._get_focus_stats(user_id),
            self._get_calendar_stats(user_id),
            self._get_achievements(user_id),
            self._get_weekly_stats(user_id),
        )

        response = {
            "todos": todos,
            "focus": focus,
            "calendar": calendar,
            "achievements": achievements,
            "activity_feed": activity_feed,
            "weekly_stats": weekly_stats,
        }

        await redis_client.setex(
            cache_key,
            300,
            json.dumps(response, default=str)
        )

        return response

    # ---------------- TODOS ----------------
    async def _get_todo_stats(self, user_id):
        result = await self.db.execute(
            select(
                func.count(Todo.id),
                func.sum(case((Todo.is_completed == True, 1), else_=0)),
                func.sum(case((Todo.is_completed == False, 1), else_=0)),
                func.sum(case((Todo.due_date < datetime.utcnow(), 1), else_=0)),
            ).where(Todo.user_id == user_id)
        )

        total, completed, pending, overdue = result.first()

        return {
            "total": total or 0,
            "completed": completed or 0,
            "pending": pending or 0,
            "overdue": overdue or 0,
        }

    # ---------------- FOCUS ----------------
    async def _get_focus_stats(self, user_id):
        week_start = datetime.utcnow() - timedelta(days=7)

        result = await self.db.execute(
            select(
                func.count(FocusSession.id),
                func.sum(FocusSession.duration_minutes),
                func.avg(FocusSession.productivity_score),
            ).where(
                FocusSession.user_id == user_id,
                FocusSession.created_at >= week_start,
            )
        )

        sessions, minutes, score = result.first()

        return {
            "sessions_this_week": sessions or 0,
            "total_focus_minutes": minutes or 0,
            "productivity_score": int(score or 0),
        }

    # ---------------- CALENDAR ----------------
    async def _get_calendar_stats(self, user_id):
        today = datetime.utcnow().date()

        today_events_result = await self.db.execute(
            select(func.count(Event.id)).where(
                Event.user_id == user_id,
                Event.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0),
            )
        )

        upcoming_result = await self.db.execute(
            select(Event).where(
                Event.user_id == user_id,
                Event.start_time >= datetime.utcnow(),
            ).order_by(Event.start_time).limit(5)
        )

        today_events = today_events_result.scalar() or 0
        upcoming = upcoming_result.scalars().all()

        return {
            "today_events": today_events,
            "upcoming_events": [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "start_time": e.start_time,
                }
                for e in upcoming
            ],
        }

    # ---------------- ACHIEVEMENTS ----------------
    async def _get_achievements(self, user_id):
        result = await self.db.execute(
            select(Achievement)
            .where(Achievement.user_id == user_id)
            .order_by(Achievement.earned_at.desc())
            .limit(10)
        )

        return [
            {
                "name": a.name,
                "earned_at": a.earned_at,
            }
            for a in result.scalars().all()
        ]

    # ---------------- ACTIVITY FEED ----------------

    # ---------------- WEEKLY STATS ----------------
    async def _get_weekly_stats(self, user_id):
        week_start = datetime.utcnow() - timedelta(days=7)

        result = await self.db.execute(
            select(
                func.date(FocusSession.created_at),
                func.count(FocusSession.id),
            )
            .where(
                FocusSession.user_id == user_id,
                FocusSession.created_at >= week_start,
            )
            .group_by(func.date(FocusSession.created_at))
            .order_by(func.date(FocusSession.created_at))
        )

        rows = result.all()

        focus_trend = [r[1] for r in rows]

        completion_result = await self.db.execute(
            select(func.avg(
                func.case((Todo.is_completed == True, 1), else_=0)
            )).where(
                Todo.user_id == user_id,
                Todo.created_at >= week_start,
            )
        )

        task_completion_rate = float(completion_result.scalar() or 0)

        return {
            "focus_trend": focus_trend,
            "task_completion_rate": task_completion_rate,
        }