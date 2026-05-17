import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_segment import RiskSegment


class RiskSegmentRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(
        self,
        *,
        is_demo: bool | None = None,
        min_probability: float = 0.45,
    ) -> list[RiskSegment]:
        from sqlalchemy import func

        latest = select(func.max(RiskSegment.computed_at).label("computed_at"))
        if is_demo is not None:
            latest = latest.where(RiskSegment.is_demo == is_demo)
        latest_subq = latest.subquery()

        q = (
            select(RiskSegment)
            .join(latest_subq, RiskSegment.computed_at == latest_subq.c.computed_at)
            .where(
                RiskSegment.probability >= min_probability,
            )
            .order_by(RiskSegment.probability.desc(), RiskSegment.computed_at.desc())
        )
        if is_demo is not None:
            q = q.where(RiskSegment.is_demo == is_demo)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def insert(self, segment: RiskSegment) -> RiskSegment:
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def deactivate_by_corridor(
        self,
        corridor_id: uuid.UUID,
        *,
        is_demo: bool = False,
    ) -> None:
        await self.session.execute(
            update(RiskSegment)
            .where(
                RiskSegment.corridor_id == corridor_id,
                RiskSegment.is_active == True,  # noqa: E712
                RiskSegment.is_demo == is_demo,
            )
            .values(is_active=False)
        )
