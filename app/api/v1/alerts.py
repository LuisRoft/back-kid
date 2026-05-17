import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import AlertRepo
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_active_alerts(
    is_demo: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    repo = AlertRepo(db)
    return await repo.list_active(is_demo=is_demo)


@router.get("/corridor/{corridor_id}", response_model=list[AlertOut])
async def list_alerts_for_corridor(
    corridor_id: uuid.UUID,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    repo = AlertRepo(db)
    return await repo.list_by_corridor(corridor_id, active_only=active_only)
