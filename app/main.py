import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.pipeline.processors.susceptibility as susc_mod
    from app.pipeline.scheduler import build_scheduler
    from app.pipeline.tasks.seed_demo import run_seed_demo
    from app.pipeline.tasks.seed_zones import run_seed_zones

    try:
        raster = await asyncio.to_thread(susc_mod.load_ecuador_raster)
        susc_mod.init(raster)
    except FileNotFoundError as exc:
        log.critical(
            "Susceptibility raster unavailable — pipeline will run without LHASA weighting: %s", exc
        )

    scheduler = build_scheduler()
    scheduler.start()

    if settings.SEED_BASELINE_DATA or settings.DEMO_MODE:
        await run_seed_demo()
        await run_seed_zones()

    if settings.RUN_PIPELINE_ON_STARTUP:
        from app.pipeline.tasks.lhasa_realtime_task import run_lhasa_realtime_task
        from app.pipeline.tasks.pois_task import run_pois_refresh_task
        from app.pipeline.tasks.realtime_rain_task import run_realtime_rain_task
        from app.pipeline.tasks.risk_task import run_risk_pipeline
        from app.pipeline.tasks.zone_risk_task import run_zone_risk_task

        for task in (
            run_pois_refresh_task,
            run_realtime_rain_task,
            run_risk_pipeline,
            run_zone_risk_task,
            run_lhasa_realtime_task,
        ):
            try:
                await task()
            except Exception:
                log.exception("Initial %s failed; scheduled runs will retry", task.__name__)

    yield

    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="back-kid",
        description="Early warning system for critical infrastructure protection",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "demo_mode": settings.DEMO_MODE}

    return app


app = create_app()
