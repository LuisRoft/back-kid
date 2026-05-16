from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: scheduler will be registered here once pipeline is built
    yield
    # Shutdown


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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers registered here as modules are built
    # from app.api.v1.router import router as v1_router
    # app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "demo_mode": settings.DEMO_MODE}

    return app


app = create_app()
