import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import CorridorRepo
from app.schemas.corridor import CorridorOut

router = APIRouter(prefix="/corridors", tags=["corridors"])


@router.get("", response_model=list[CorridorOut])
async def list_corridors(
    is_demo: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    repo = CorridorRepo(db)
    return await repo.list_all(is_demo=is_demo)


@router.get("/{corridor_id}", response_model=CorridorOut)
async def get_corridor(
    corridor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = CorridorRepo(db)
    corridor = await repo.get_by_id(corridor_id)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found")
    return corridor
