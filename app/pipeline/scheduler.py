import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    from app.pipeline.tasks.risk_task import run_risk_pipeline

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        run_risk_pipeline,
        IntervalTrigger(hours=6),
        id="risk_pipeline",
        replace_existing=True,
        max_instances=1,          # never overlap
        misfire_grace_time=300,   # tolerate up to 5 min delay
    )

    log.info("Scheduler configured — risk_pipeline every 6 h")
    return scheduler
