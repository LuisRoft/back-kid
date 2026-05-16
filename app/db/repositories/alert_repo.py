import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


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
