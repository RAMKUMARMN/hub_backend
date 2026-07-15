from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import AsyncSessionLocal
from app.services.todo_reminder_service import create_due_soon_notifications
from app.websocket_manager import manager

scheduler = AsyncIOScheduler(timezone="UTC")


async def reminder_job() -> None:
    print("⏰ Scheduler triggered")

    async with AsyncSessionLocal() as db:
        await create_due_soon_notifications(db, manager)


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.add_job(
        reminder_job,
        trigger="interval",
        minutes=1,  # use 1 minute while testing; 5 minutes is fine later
        id="todo_reminder_job",
        replace_existing=True,
        max_instances=1,       # prevents overlapping runs
        coalesce=True,         # combines missed runs into one
        misfire_grace_time=60, # allows a job delayed by up to 60 seconds
    )

    scheduler.start()
    print("Todo reminder scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)