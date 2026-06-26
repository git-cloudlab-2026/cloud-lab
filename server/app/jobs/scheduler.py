import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs.lifecycle import VmLifecycleJob

logger = logging.getLogger(__name__)


async def run_lifecycle_once() -> None:
    async with SessionLocal() as session:
        job = VmLifecycleJob(session)
        destroyed = await job.destroy_due_vms()
        if destroyed:
            logger.info("Lifecycle: %s VM detruite(s) automatiquement.", len(destroyed))


def create_scheduler() -> AsyncIOScheduler | None:
    settings = get_settings()
    if not settings.lifecycle_scheduler_enabled:
        return None

    scheduler = AsyncIOScheduler(timezone="Europe/Zurich")
    scheduler.add_job(
        run_lifecycle_once,
        "interval",
        seconds=settings.lifecycle_scheduler_interval_seconds,
        id="vm_lifecycle_destroy_due_vms",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
