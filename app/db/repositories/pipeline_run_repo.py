from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_run import PipelineRun


class PipelineRunRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(self, task_name: str) -> PipelineRun:
        run = PipelineRun(task_name=task_name, status="running")
        self.session.add(run)
        await self.session.flush()
        return run

    async def complete(
        self, run_id: int, *, success: bool, error_message: str | None = None
    ) -> None:
        result = await self.session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        run = result.scalar_one()
        run.status = "success" if success else "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def get_latest(self, task_name: str) -> PipelineRun | None:
        result = await self.session.execute(
            select(PipelineRun)
            .where(PipelineRun.task_name == task_name)
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, *, limit: int = 50) -> list[PipelineRun]:
        result = await self.session.execute(
            select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
