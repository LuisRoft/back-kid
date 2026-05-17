import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


@dataclass
class AlertWithCorridor:
    id: int
    corridor_id: uuid.UUID
    corridor_name: str
    population_impact: int
    probability: float
    horizon_hours: int
    generated_at: datetime
    is_active: bool
    is_demo: bool


class AlertRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, *, is_demo: bool | None = None) -> list[Alert]:
        q = select(Alert).where(Alert.is_active == True).order_by(Alert.generated_at.desc())  # noqa: E712
        if is_demo is not None:
            q = q.where(Alert.is_demo == is_demo)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_by_corridor(
        self, corridor_id: uuid.UUID, *, active_only: bool = True
    ) -> list[Alert]:
        q = select(Alert).where(Alert.corridor_id == corridor_id)
        if active_only:
            q = q.where(Alert.is_active == True)  # noqa: E712
        result = await self.session.execute(q.order_by(Alert.generated_at.desc()))
        return list(result.scalars().all())

    async def insert(self, alert: Alert) -> Alert:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def list_active_with_corridor(
        self, *, is_demo: bool | None = None
    ) -> list[AlertWithCorridor]:
        """Active alerts joined with corridor name and population_impact."""
        from app.models.corridor import Corridor

        q = (
            select(
                Alert,
                Corridor.name.label("corridor_name"),
                Corridor.population_impact.label("population_impact"),
            )
            .join(Corridor, Alert.corridor_id == Corridor.id)
            .where(Alert.is_active == True)  # noqa: E712
            .order_by(Alert.probability.desc())
        )
        if is_demo is not None:
            q = q.where(Alert.is_demo == is_demo)

        result = await self.session.execute(q)
        return [
            AlertWithCorridor(
                id=row.Alert.id,
                corridor_id=row.Alert.corridor_id,
                corridor_name=row.corridor_name,
                population_impact=row.population_impact,
                probability=row.Alert.probability,
                horizon_hours=row.Alert.horizon_hours,
                generated_at=row.Alert.generated_at,
                is_active=row.Alert.is_active,
                is_demo=row.Alert.is_demo,
            )
            for row in result
        ]

    async def deactivate_by_corridor(
        self, corridor_id: uuid.UUID, *, is_demo: bool = False
    ) -> None:
        await self.session.execute(
            update(Alert)
            .where(
                Alert.corridor_id == corridor_id,
                Alert.is_active == True,  # noqa: E712
                Alert.is_demo == is_demo,
            )
            .values(is_active=False)
        )
