from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscriber import Subscriber


class SubscriberRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Subscriber]:
        result = await self.session.execute(
            select(Subscriber).where(Subscriber.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def insert(self, subscriber: Subscriber) -> Subscriber:
        self.session.add(subscriber)
        await self.session.flush()
        return subscriber
