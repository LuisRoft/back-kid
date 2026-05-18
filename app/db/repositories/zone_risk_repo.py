import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone_risk_forecast import ZoneRiskForecast


class ZoneRiskRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest_by_zone(self, zone_id: uuid.UUID) -> ZoneRiskForecast | None:
        result = await self.session.execute(
            select(ZoneRiskForecast)
            .where(ZoneRiskForecast.zone_id == zone_id)
            .order_by(ZoneRiskForecast.computed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def insert(self, forecast: ZoneRiskForecast) -> ZoneRiskForecast:
        self.session.add(forecast)
        await self.session.flush()
        return forecast

    async def deactivate_by_zone(self, zone_id: uuid.UUID) -> None:
        await self.session.execute(
            update(ZoneRiskForecast)
            .where(
                ZoneRiskForecast.zone_id == zone_id,
                ZoneRiskForecast.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )

    async def list_active(
        self,
        *,
        horizon_hours: int | None = None,
        min_probability: float = 0.0,
    ) -> list[ZoneRiskForecast]:
        """Latest active forecast per zone (× horizon) at or above min_probability."""
        subq_base = select(
            ZoneRiskForecast.zone_id,
            ZoneRiskForecast.horizon_hours,
            func.max(ZoneRiskForecast.computed_at).label("max_computed_at"),
        ).where(ZoneRiskForecast.is_active == True)  # noqa: E712

        if horizon_hours is not None:
            subq_base = subq_base.where(ZoneRiskForecast.horizon_hours == horizon_hours)

        subq = subq_base.group_by(
            ZoneRiskForecast.zone_id, ZoneRiskForecast.horizon_hours
        ).subquery()

        q = (
            select(ZoneRiskForecast)
            .join(
                subq,
                (ZoneRiskForecast.zone_id == subq.c.zone_id)
                & (ZoneRiskForecast.horizon_hours == subq.c.horizon_hours)
                & (ZoneRiskForecast.computed_at == subq.c.max_computed_at),
            )
            .where(
                ZoneRiskForecast.is_active == True,  # noqa: E712
                ZoneRiskForecast.probability >= min_probability,
            )
            .order_by(ZoneRiskForecast.probability.desc())
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_by_zone(
        self, zone_id: uuid.UUID, *, only_active: bool = True
    ) -> list[ZoneRiskForecast]:
        q = select(ZoneRiskForecast).where(ZoneRiskForecast.zone_id == zone_id)
        if only_active:
            q = q.where(ZoneRiskForecast.is_active == True)  # noqa: E712
        q = q.order_by(ZoneRiskForecast.horizon_hours.asc())
        result = await self.session.execute(q)
        return list(result.scalars().all())
