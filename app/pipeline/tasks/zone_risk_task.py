"""Zone risk task — computes risk score per administrative zone × horizon.

Runs after the main risk pipeline. Uses the same Open-Meteo forecast + LHASA
susceptibility weighting, but aggregated over points sampled inside each zone
polygon.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
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
    fresh_cutoff = now - timedelta(hours=24)
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
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    log.warning(
                        "Open-Meteo quota exhausted at zone %s — stopping this run, will retry next schedule",
                        zone.code,
                    )
                    break
                log.exception("Open-Meteo HTTP error for zone %s — skipping", zone.code)
                continue
            except Exception:
                log.exception("Open-Meteo failed for zone %s — skipping", zone.code)
                continue

            sample_precipitation = [aggregate_precipitation(f) for f in forecasts]
            breakdown = aggregate_zone_probabilities(sample_precipitation, points)

            await risk_repo.deactivate_by_zone(zone.id)
            for horizon, data in breakdown.items():
                await risk_repo.insert(
                    ZoneRiskForecast(
                        zone_id=zone.id,
                        horizon_hours=horizon,
                        probability=data["probability"],
                        expected_rainfall_mm=data["expected_rainfall_mm"],
                        peak_susceptibility_class=data["peak_susceptibility_class"],
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


if __name__ == "__main__":
    # Allow running standalone: `uv run python -m app.pipeline.tasks.zone_risk_task`
    import logging as _logging
    from app.pipeline.processors import susceptibility as _susc

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)-7s %(name)s — %(message)s")
    try:
        _susc.init(_susc.load_ecuador_raster())
    except FileNotFoundError:
        log.warning("LHASA susceptibility raster missing — running without weighting")
    asyncio.run(run_zone_risk_task())
