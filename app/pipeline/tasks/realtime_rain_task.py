"""Realtime rain task — samples Open-Meteo current precipitation over the
national grid and inserts a snapshot row per point into `realtime_rain_samples`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geoalchemy2 import WKTElement

from app.config import settings
from app.db.repositories.realtime_rain_repo import RealtimeRainRepo
from app.db.session import AsyncSessionLocal
from app.integrations.open_meteo import build_national_grid, get_current_precipitation_grid
from app.models.realtime_rain_sample import RealtimeRainSample

log = logging.getLogger(__name__)


async def run_realtime_rain_task() -> None:
    log.info("Realtime rain task started")
    grid = build_national_grid(settings.ecuador_bbox, settings.OPEN_METEO_GRID_STEP_DEG)
    try:
        forecasts = await get_current_precipitation_grid(grid)
    except Exception:
        log.exception("Open-Meteo current grid fetch failed — skipping run")
        return

    samples = list(_to_samples(grid, forecasts))
    if not samples:
        log.warning("Realtime rain task produced 0 samples — nothing to insert")
        return

    async with AsyncSessionLocal() as session:
        try:
            await RealtimeRainRepo(session).bulk_insert(samples)
            await session.commit()
            log.info("Realtime rain task inserted %d samples", len(samples))
        except Exception:
            await session.rollback()
            log.exception("Realtime rain task failed — rolled back")
            raise


def _to_samples(
    grid: list[tuple[float, float]], forecasts: list[dict]
) -> list[RealtimeRainSample]:
    out: list[RealtimeRainSample] = []
    for (lat, lon), forecast in zip(grid, forecasts, strict=False):
        current = forecast.get("current") or {}
        precipitation = current.get("precipitation")
        if precipitation is None:
            continue
        observed_at = _parse_time(current.get("time")) or datetime.now(timezone.utc)
        out.append(
            RealtimeRainSample(
                geometry=WKTElement(f"POINT({lon} {lat})", srid=4326),
                lat=lat,
                lon=lon,
                precipitation_mm_h=float(precipitation),
                observed_at=observed_at,
            )
        )
    return out


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Open-Meteo returns local ISO without timezone — treat as UTC for storage simplicity.
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
