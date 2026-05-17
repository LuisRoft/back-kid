from datetime import datetime, timedelta, timezone

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_Intersects, ST_MakeEnvelope, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.realtime_rain_sample import RealtimeRainSample


class RealtimeRainRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, samples: list[RealtimeRainSample]) -> None:
        self.session.add_all(samples)
        await self.session.flush()

    async def latest_by_bbox(
        self,
        *,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        within_minutes: int = 90,
    ) -> list[RealtimeRainSample]:
        envelope = ST_SetSRID(ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat), 4326)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        q = (
            select(RealtimeRainSample)
            .where(
                ST_Intersects(RealtimeRainSample.geometry, envelope),
                RealtimeRainSample.observed_at >= cutoff,
            )
            .order_by(RealtimeRainSample.observed_at.desc())
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def latest_near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 10.0,
        within_minutes: int = 90,
        limit: int = 20,
    ) -> list[RealtimeRainSample]:
        # ST_DWithin with geography cast for meters
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        q = (
            select(RealtimeRainSample)
            .where(
                ST_DWithin(
                    cast(RealtimeRainSample.geometry, Geography),
                    cast(point, Geography),
                    radius_km * 1000.0,
                ),
                RealtimeRainSample.observed_at >= cutoff,
            )
            .order_by(RealtimeRainSample.observed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())
