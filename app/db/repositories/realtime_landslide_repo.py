from datetime import datetime, timedelta, timezone

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_Intersects, ST_MakeEnvelope, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.realtime_landslide_event import RealtimeLandslideEvent


class RealtimeLandslideRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, events: list[RealtimeLandslideEvent]) -> None:
        self.session.add_all(events)
        await self.session.flush()

    async def recent(
        self,
        *,
        hours: int = 24,
        min_lon: float | None = None,
        min_lat: float | None = None,
        max_lon: float | None = None,
        max_lat: float | None = None,
    ) -> list[RealtimeLandslideEvent]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = select(RealtimeLandslideEvent).where(RealtimeLandslideEvent.reported_at >= cutoff)
        if None not in (min_lon, min_lat, max_lon, max_lat):
            envelope = ST_SetSRID(ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat), 4326)
            q = q.where(ST_Intersects(RealtimeLandslideEvent.geometry, envelope))
        q = q.order_by(RealtimeLandslideEvent.reported_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def recent_near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 50.0,
        hours: int = 24,
        limit: int = 20,
    ) -> list[RealtimeLandslideEvent]:
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = (
            select(RealtimeLandslideEvent)
            .where(
                ST_DWithin(
                    cast(RealtimeLandslideEvent.geometry, Geography),
                    cast(point, Geography),
                    radius_km * 1000.0,
                ),
                RealtimeLandslideEvent.reported_at >= cutoff,
            )
            .order_by(RealtimeLandslideEvent.reported_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())
