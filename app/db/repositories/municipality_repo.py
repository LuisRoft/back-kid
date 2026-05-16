import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.municipality import Municipality


class MunicipalityRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Municipality]:
        result = await self.session.execute(select(Municipality))
        return list(result.scalars().all())

    async def get_by_id(self, municipality_id: uuid.UUID) -> Municipality | None:
        result = await self.session.execute(
            select(Municipality).where(Municipality.id == municipality_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, municipality: Municipality) -> Municipality:
        self.session.add(municipality)
        await self.session.flush()
        return municipality
