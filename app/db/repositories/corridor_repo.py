import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corridor import Corridor

DEMO_CORRIDOR_PREFIX = "demo-2023:"


class CorridorRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, is_demo: bool | None = None) -> list[Corridor]:
        q = select(Corridor)
        if is_demo is not None:
            q = q.where(Corridor.is_demo == is_demo)
        if is_demo is True:
            q = q.where(Corridor.osm_id.like(f"{DEMO_CORRIDOR_PREFIX}%"))
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_id(self, corridor_id: uuid.UUID) -> Corridor | None:
        result = await self.session.execute(
            select(Corridor).where(Corridor.id == corridor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_osm_id(self, osm_id: str) -> Corridor | None:
        result = await self.session.execute(
            select(Corridor).where(Corridor.osm_id == osm_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, corridor: Corridor) -> Corridor:
        self.session.add(corridor)
        await self.session.flush()
        return corridor
