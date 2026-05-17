"""LHASA NRT task — synthesizes near-real-time landslide events by combining
the in-memory susceptibility raster with the most recent rain samples.

When a true LHASA NRT feed becomes available, swap the `synthesize_events_*`
call for the real fetch — the rest of the pipeline (storage, API, agent) stays
the same.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.realtime_landslide_repo import RealtimeLandslideRepo
from app.db.session import AsyncSessionLocal
from app.integrations.lhasa import synthesize_events_from_rain
from app.models.realtime_landslide_event import RealtimeLandslideEvent
from app.models.realtime_rain_sample import RealtimeRainSample

log = logging.getLogger(__name__)

# Window of rain samples to consider per run.
RAIN_LOOKBACK_MINUTES = 90


async def run_lhasa_realtime_task() -> None:
    log.info("LHASA NRT task started")
    async with AsyncSessionLocal() as session:
        try:
            count = await _run(session)
            await session.commit()
            log.info("LHASA NRT task inserted %d events", count)
        except Exception:
            await session.rollback()
            log.exception("LHASA NRT task failed — rolled back")
            raise


async def _run(session: AsyncSession) -> int:
    rain_rows = await _recent_rain(session)
    events = synthesize_events_from_rain(rain_rows)
    if not events:
        return 0

    landslide_repo = RealtimeLandslideRepo(session)
    rows: list[RealtimeLandslideEvent] = [
        RealtimeLandslideEvent(
            geometry=WKTElement(f"POINT({event['lon']} {event['lat']})", srid=4326),
            lat=event["lat"],
            lon=event["lon"],
            severity=event["severity"],
            source=event["source"],
            reported_at=event["reported_at"],
        )
        for event in events
    ]
    await landslide_repo.bulk_insert(rows)
    return len(rows)


async def _recent_rain(
    session: AsyncSession,
) -> list[tuple[float, float, float, datetime]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RAIN_LOOKBACK_MINUTES)
    q = (
        select(RealtimeRainSample)
        .where(RealtimeRainSample.observed_at >= cutoff)
        .order_by(RealtimeRainSample.observed_at.desc())
    )
    result = await session.execute(q)
    rows = result.scalars().all()
    return [(r.lat, r.lon, r.precipitation_mm_h, r.observed_at) for r in rows]
