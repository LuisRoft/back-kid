import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import AlertRepo
from app.schemas.alert import AlertOut, AlertWithCorridorOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertWithCorridorOut])
async def list_active_alerts(
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    """Active alerts sorted by probability descending, with corridor name and population impact."""
    repo = AlertRepo(db)
    return await repo.list_active_with_corridor(is_demo=is_demo)


@router.get("/corridor/{corridor_id}", response_model=list[AlertOut])
async def list_alerts_for_corridor(
    corridor_id: uuid.UUID,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    repo = AlertRepo(db)
    return await repo.list_by_corridor(corridor_id, active_only=active_only)
