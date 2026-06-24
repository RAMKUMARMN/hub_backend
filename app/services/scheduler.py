from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.websocket_manager import manager
from app.database import AsyncSessionLocal
from app.services.todo_reminder_service import create_due_soon_notifications

scheduler = AsyncIOScheduler()


async def reminder_job():
    async with AsyncSessionLocal() as db:
        await create_due_soon_notifications(db,manager)


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            reminder_job,
            "interval",
            minutes=5,
            id="todo_reminder_job",
            replace_existing=True,
        )

        
    scheduler.start()
    print("Scheduler started ✅")


def stop_scheduler():
    scheduler.shutdown()