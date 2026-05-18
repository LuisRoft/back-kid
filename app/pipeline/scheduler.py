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
    now = datetime.now(timezone.utc)

    # When RUN_PIPELINE_ON_STARTUP=false we explicitly want NO automatic runs
    # right after boot — push each job's first fire one full interval into the
    # future so the developer can restart freely without burning quotas.
    early_zone_offset = timedelta(minutes=3) if settings.RUN_PIPELINE_ON_STARTUP else timedelta(hours=settings.ZONE_RISK_INTERVAL_HOURS)
    rain_offset       = timedelta(seconds=10) if settings.RUN_PIPELINE_ON_STARTUP else timedelta(minutes=settings.REALTIME_RAIN_INTERVAL_MINUTES)
    lhasa_offset      = timedelta(seconds=10) if settings.RUN_PIPELINE_ON_STARTUP else timedelta(minutes=settings.LHASA_NRT_INTERVAL_MINUTES)
    risk_offset       = timedelta(seconds=10) if settings.RUN_PIPELINE_ON_STARTUP else timedelta(minutes=settings.PIPELINE_INTERVAL_MINUTES)
    pois_offset       = timedelta(seconds=10) if settings.RUN_PIPELINE_ON_STARTUP else timedelta(days=settings.POIS_REFRESH_INTERVAL_DAYS)

    scheduler.add_job(
        run_risk_pipeline,
        IntervalTrigger(
            minutes=settings.PIPELINE_INTERVAL_MINUTES,
            start_date=now + risk_offset,
        ),
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
            start_date=now + early_zone_offset,
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
        IntervalTrigger(
            minutes=settings.REALTIME_RAIN_INTERVAL_MINUTES,
            start_date=now + rain_offset,
        ),
        id="realtime_rain",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # LHASA NRT events — synthesized from rain + susceptibility for now.
    scheduler.add_job(
        run_lhasa_realtime_task,
        IntervalTrigger(
            minutes=settings.LHASA_NRT_INTERVAL_MINUTES,
            start_date=now + lhasa_offset,
        ),
        id="lhasa_realtime",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    # POIs from Overpass — weekly refresh.
    scheduler.add_job(
        run_pois_refresh_task,
        IntervalTrigger(
            days=settings.POIS_REFRESH_INTERVAL_DAYS,
            start_date=now + pois_offset,
        ),
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
