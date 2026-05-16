import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rerouting_plan import ReroutingPlan


class ReroutingPlanRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_corridor(self, corridor_id: uuid.UUID) -> ReroutingPlan | None:
        result = await self.session.execute(
            select(ReroutingPlan).where(ReroutingPlan.corridor_id == corridor_id)
        )
        return result.scalar_one_or_none()

    async def list_for_corridors(
        self, corridor_ids: list[uuid.UUID]
    ) -> list[ReroutingPlan]:
        result = await self.session.execute(
            select(ReroutingPlan).where(ReroutingPlan.corridor_id.in_(corridor_ids))
        )
        return list(result.scalars().all())

    async def upsert(self, plan: ReroutingPlan) -> ReroutingPlan:
        """Atomic upsert — safe under concurrent pipeline runs."""
        stmt = (
            pg_insert(ReroutingPlan)
            .values(
                corridor_id=plan.corridor_id,
                geometry=plan.geometry,
                distance_km=plan.distance_km,
                duration_minutes=plan.duration_minutes,
                via_description=plan.via_description,
            )
            .on_conflict_do_update(
                index_elements=["corridor_id"],
                set_=dict(
                    geometry=plan.geometry,
                    distance_km=plan.distance_km,
                    duration_minutes=plan.duration_minutes,
                    via_description=plan.via_description,
                ),
            )
            .returning(ReroutingPlan)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
