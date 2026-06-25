import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs.lifecycle import VmLifecycleJob

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Zurich")


async def run_lifecycle_job() -> None:
    async with SessionLocal() as session:
        result = await VmLifecycleJob(session).run()
        await session.commit()
        logger.info(
            "Lifecycle job finished: %s expiring soon, %s expired",
            result["expiring_soon"],
            result["expired"],
        )


def start_scheduler() -> None:
    settings = get_settings()
    if not settings.lifecycle_scheduler_enabled:
        logger.info("Lifecycle scheduler disabled")
        return
    if scheduler.running:
        return

    scheduler.add_job(
        run_lifecycle_job,
        "interval",
        seconds=settings.lifecycle_scheduler_interval_seconds,
        id="lifecycle-hourly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # Extinction nuit/week-end: garde-fou planifie, l'action infra reste volontairement
    # separee tant que Terraform/Ansible ne sont pas valides en production.
    scheduler.add_job(
        run_lifecycle_job,
        "cron",
        hour="20",
        minute="0",
        id="lifecycle-nightly-check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Lifecycle scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Lifecycle scheduler stopped")
