import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories import ForecastRepo
from app.schemas.forecast import RiskForecastOut

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

_VALID_HORIZONS = {24, 48, 72}


@router.get("", response_model=list[RiskForecastOut])
async def list_latest_forecasts(
    horizon_hours: Annotated[int, Query(description="Forecast horizon in hours: 24, 48, or 72")] = 24,
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    if horizon_hours not in _VALID_HORIZONS:
        raise HTTPException(status_code=422, detail="horizon_hours must be 24, 48, or 72")
    """Latest risk forecast per corridor for the given horizon."""
    repo = ForecastRepo(db)
    return await repo.list_latest_all(horizon_hours, is_demo=is_demo)


@router.get("/corridor/{corridor_id}", response_model=list[RiskForecastOut])
async def list_forecasts_for_corridor(
    corridor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """All three horizons (24/48/72h) for a single corridor."""
    repo = ForecastRepo(db)
    results = []
    for h in (24, 48, 72):
        forecast = await repo.get_latest_by_corridor(corridor_id, h)
        if forecast:
            results.append(forecast)
    return results
