"""Zone risk task — computes risk score per administrative zone × horizon.

Runs after the main risk pipeline. Uses the same Open-Meteo forecast + LHASA
susceptibility weighting, but aggregated over points sampled inside each zone
polygon.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.zone_repo import ZoneRepo
from app.db.repositories.zone_risk_repo import ZoneRiskRepo
from app.db.session import AsyncSessionLocal
from app.integrations.open_meteo import aggregate_precipitation, get_precipitation_forecasts
from app.models.zone_risk_forecast import ZoneRiskForecast
from app.pipeline.processors.zone_aggregator import (
    aggregate_zone_probabilities,
    sample_points_for_zone,
)

log = logging.getLogger(__name__)


async def run_zone_risk_task() -> None:
    log.info("Zone risk task started")
    async with AsyncSessionLocal() as session:
        try:
            processed = await _run(session)
            await session.commit()
            log.info("Zone risk task done — %d zones processed", processed)
        except Exception:
            await session.rollback()
            log.exception("Zone risk task failed — rolled back")
            raise


async def _run(session: AsyncSession) -> int:
    zone_repo = ZoneRepo(session)
    risk_repo = ZoneRiskRepo(session)

    # Cantons only — they are the right granularity for nation-scale display.
    # Parroquias add too many API calls for the demo; can be enabled later.
    zones = await zone_repo.list_all(level="canton")
    if not zones:
        log.info("No zones in DB — skipping zone risk task")
        return 0

    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(hours=6)
    processed = 0

    for idx, zone in enumerate(zones):
        if idx > 0:
            await asyncio.sleep(0.15)

        try:
            latest = await risk_repo.get_latest_by_zone(zone.id)
            if latest and latest.computed_at >= fresh_cutoff:
                processed += 1
                continue

            points = sample_points_for_zone(zone.geometry)
            if not points:
                continue

            try:
                forecasts = await get_precipitation_forecasts(points)
            except Exception:
                log.exception("Open-Meteo failed for zone %s — skipping", zone.code)
                continue

            sample_precipitation = [aggregate_precipitation(f) for f in forecasts]
            peaks = aggregate_zone_probabilities(sample_precipitation, points)

            await risk_repo.deactivate_by_zone(zone.id)
            for horizon, probability in peaks.items():
                await risk_repo.insert(
                    ZoneRiskForecast(
                        zone_id=zone.id,
                        horizon_hours=horizon,
                        probability=probability,
                        computed_at=now,
                        valid_from=now + timedelta(hours=horizon - 24),
                        is_active=True,
                        is_demo=False,
                    )
                )
            processed += 1
        except Exception:
            log.exception("Failed to process zone %s (%s)", zone.code, zone.name)
            continue

    return processed
