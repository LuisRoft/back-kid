import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import ReroutingPlanRepo
from app.schemas.rerouting_plan import ReroutingPlanOut

router = APIRouter(prefix="/rerouting", tags=["rerouting"])


@router.get("/corridor/{corridor_id}", response_model=ReroutingPlanOut)
async def get_rerouting_plan(
    corridor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = ReroutingPlanRepo(db)
    plan = await repo.get_by_corridor(corridor_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No rerouting plan for this corridor")
    return plan
