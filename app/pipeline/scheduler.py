import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

log = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    from app.pipeline.tasks.lhasa_realtime_task import run_lhasa_realtime_task
    from app.pipeline.tasks.pois_task import run_pois_refresh_task
    from app.pipeline.tasks.realtime_rain_task import run_realtime_rain_task
    from app.pipeline.tasks.risk_task import run_risk_pipeline
    from app.pipeline.tasks.zone_risk_task import run_zone_risk_task

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        run_risk_pipeline,
        IntervalTrigger(minutes=settings.PIPELINE_INTERVAL_MINUTES),
        id="risk_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Zone risk computes per-canton scores. ~221 cantons × ~6 points each adds
    # up fast on Open-Meteo's free tier, so we run it every 6h (4×/day) instead
    # of every 30 min. Administrative-scale risk doesn't change faster than that.
    scheduler.add_job(
        run_zone_risk_task,
        IntervalTrigger(
            hours=settings.ZONE_RISK_INTERVAL_HOURS,
            start_date=datetime.now(timezone.utc) + timedelta(minutes=3),
        ),
        id="zone_risk",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    # Realtime rain — current precipitation snapshot over national grid.
    scheduler.add_job(
        run_realtime_rain_task,
        IntervalTrigger(minutes=settings.REALTIME_RAIN_INTERVAL_MINUTES),
        id="realtime_rain",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # LHASA NRT events — synthesized from rain + susceptibility for now.
    scheduler.add_job(
        run_lhasa_realtime_task,
        IntervalTrigger(minutes=settings.LHASA_NRT_INTERVAL_MINUTES),
        id="lhasa_realtime",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    # POIs from Overpass — weekly refresh.
    scheduler.add_job(
        run_pois_refresh_task,
        IntervalTrigger(days=settings.POIS_REFRESH_INTERVAL_DAYS),
        id="pois_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    log.info(
        "Scheduler configured — risk_pipeline=%dm zone_risk=%dh realtime_rain=%dm lhasa_nrt=%dm pois=%dd",
        settings.PIPELINE_INTERVAL_MINUTES,
        settings.ZONE_RISK_INTERVAL_HOURS,
        settings.REALTIME_RAIN_INTERVAL_MINUTES,
        settings.LHASA_NRT_INTERVAL_MINUTES,
        settings.POIS_REFRESH_INTERVAL_DAYS,
    )
    return scheduler
