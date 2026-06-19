from datetime import datetime
from pydantic import BaseModel


class TodoStats(BaseModel):
    total: int
    completed: int
    pending: int
    overdue: int


class FocusStats(BaseModel):
    sessions_this_week: int
    total_focus_minutes: int
    productivity_score: int


class UpcomingEvent(BaseModel):
    id: str
    title: str
    start_time: datetime


class CalendarStats(BaseModel):
    today_events: int
    upcoming_events: list[UpcomingEvent]


class AchievementItem(BaseModel):
    name: str
    earned_at: datetime


class ActivityFeedItem(BaseModel):
    action: str
    resource: str
    timestamp: datetime


class WeeklyStats(BaseModel):
    focus_trend: list[int]
    task_completion_rate: float


class DashboardResponse(BaseModel):
    todos: TodoStats
    focus: FocusStats
    calendar: CalendarStats
    achievements: list[AchievementItem]
    activity_feed: list[ActivityFeedItem]
    weekly_stats: WeeklyStats