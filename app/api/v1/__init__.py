from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.corridors import router as corridors_router
from app.api.v1.forecasts import router as forecasts_router
from app.api.v1.map import router as map_router
from app.api.v1.municipalities import router as municipalities_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.rerouting import router as rerouting_router

router = APIRouter()

router.include_router(map_router)
router.include_router(corridors_router)
router.include_router(forecasts_router)
router.include_router(alerts_router)
router.include_router(municipalities_router)
router.include_router(rerouting_router)
router.include_router(pipeline_router)
