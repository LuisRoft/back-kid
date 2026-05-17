from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import PipelineRunRepo
from app.schemas.pipeline_run import PipelineRunOut

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/runs", response_model=list[PipelineRunOut])
async def list_pipeline_runs(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    db: AsyncSession = Depends(get_db),
):
    repo = PipelineRunRepo(db)
    return await repo.list_recent(limit=limit)
