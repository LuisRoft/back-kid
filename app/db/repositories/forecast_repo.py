import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_forecast import RiskForecast


class ForecastRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest_by_corridor(
        self, corridor_id: uuid.UUID, horizon_hours: int
    ) -> RiskForecast | None:
        result = await self.session.execute(
            select(RiskForecast)
            .where(
                RiskForecast.corridor_id == corridor_id,
                RiskForecast.horizon_hours == horizon_hours,
            )
            .order_by(RiskForecast.computed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_latest_all(
        self,
        horizon_hours: int,
        *,
        is_demo: bool | None = None,
    ) -> list[RiskForecast]:
        """Latest forecast per corridor for the given horizon."""
        from sqlalchemy import func
        from sqlalchemy.orm import aliased

        subq = (
            select(
                RiskForecast.corridor_id,
                func.max(RiskForecast.computed_at).label("max_computed_at"),
            )
            .where(RiskForecast.horizon_hours == horizon_hours)
            .group_by(RiskForecast.corridor_id)
            .subquery()
        )

        q = (
            select(RiskForecast)
            .join(
                subq,
                (RiskForecast.corridor_id == subq.c.corridor_id)
                & (RiskForecast.computed_at == subq.c.max_computed_at),
            )
            .where(RiskForecast.horizon_hours == horizon_hours)
        )
        if is_demo is not None:
            q = q.where(RiskForecast.is_demo == is_demo)

        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def insert(self, forecast: RiskForecast) -> RiskForecast:
        self.session.add(forecast)
        await self.session.flush()
        return forecast
