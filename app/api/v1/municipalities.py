import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import MunicipalityRepo
from app.schemas.municipality import MunicipalityOut

router = APIRouter(prefix="/municipalities", tags=["municipalities"])


@router.get("", response_model=list[MunicipalityOut])
async def list_municipalities(db: AsyncSession = Depends(get_db)):
    repo = MunicipalityRepo(db)
    return await repo.list_all()


@router.get("/{municipality_id}", response_model=MunicipalityOut)
async def get_municipality(
    municipality_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = MunicipalityRepo(db)
    mun = await repo.get_by_id(municipality_id)
    if not mun:
        raise HTTPException(status_code=404, detail="Municipality not found")
    return mun
