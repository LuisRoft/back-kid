import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

log = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    from app.pipeline.tasks.risk_task import run_risk_pipeline

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        run_risk_pipeline,
        IntervalTrigger(minutes=settings.PIPELINE_INTERVAL_MINUTES),
        id="risk_pipeline",
        replace_existing=True,
        max_instances=1,          # never overlap
        misfire_grace_time=300,   # tolerate up to 5 min delay
    )

    log.info("Scheduler configured — risk_pipeline every %d min", settings.PIPELINE_INTERVAL_MINUTES)
    return scheduler
