import uuid

from geoalchemy2.functions import ST_Contains, ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone import Zone


class ZoneRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, level: str | None = None) -> list[Zone]:
        q = select(Zone)
        if level is not None:
            q = q.where(Zone.level == level)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_by_bbox(
        self,
        *,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        level: str | None = None,
    ) -> list[Zone]:
        from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope

        envelope = ST_SetSRID(ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat), 4326)
        q = select(Zone).where(ST_Intersects(Zone.geometry, envelope))
        if level is not None:
            q = q.where(Zone.level == level)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def find_containing_point(self, lat: float, lon: float, *, level: str = "parroquia") -> Zone | None:
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        q = (
            select(Zone)
            .where(Zone.level == level, ST_Contains(Zone.geometry, point))
            .limit(1)
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_id(self, zone_id: uuid.UUID) -> Zone | None:
        result = await self.session.execute(select(Zone).where(Zone.id == zone_id))
        return result.scalar_one_or_none()

    async def upsert(self, zone: Zone) -> Zone:
        self.session.add(zone)
        await self.session.flush()
        return zone
