from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Intersects, ST_MakeEnvelope, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import Poi


class PoiRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_bbox_and_types(
        self,
        *,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        types: list[str] | None = None,
        limit: int = 1000,
    ) -> list[Poi]:
        envelope = ST_SetSRID(ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat), 4326)
        q = select(Poi).where(ST_Intersects(Poi.geometry, envelope))
        if types:
            q = q.where(Poi.type.in_(types))
        q = q.limit(limit)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def nearest(
        self,
        lat: float,
        lon: float,
        *,
        types: list[str] | None = None,
        k: int = 5,
        radius_km: float = 25.0,
    ) -> list[Poi]:
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        q = (
            select(Poi)
            .where(
                ST_DWithin(
                    cast(Poi.geometry, Geography),
                    cast(point, Geography),
                    radius_km * 1000.0,
                )
            )
            .order_by(
                ST_Distance(cast(Poi.geometry, Geography), cast(point, Geography))
            )
            .limit(k)
        )
        if types:
            q = q.where(Poi.type.in_(types))
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # Postgres caps prepared-statement parameters at 32767 (signed int16).
    # Each Poi row binds ~7 params, so 1000 rows/batch leaves a comfortable margin.
    _UPSERT_BATCH_SIZE = 1000

    async def upsert_from_osm(self, rows: list[dict]) -> int:
        """Upsert a batch of OSM-sourced POIs in chunks to stay under
        Postgres' 32767-parameter limit.

        Each row dict must include:
            osm_id, type, name (nullable), address (nullable),
            geometry (EWKT), source, fetched_at.
        """
        if not rows:
            return 0
        for start in range(0, len(rows), self._UPSERT_BATCH_SIZE):
            batch = rows[start : start + self._UPSERT_BATCH_SIZE]
            stmt = pg_insert(Poi.__table__).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_pois_osm_id_type",
                set_={
                    "name": stmt.excluded.name,
                    "address": stmt.excluded.address,
                    "geometry": stmt.excluded.geometry,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self.session.execute(stmt)
        return len(rows)
