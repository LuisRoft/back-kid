from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),  # .env for Docker; .env.local overrides locally
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — Supabase
    DATABASE_URL: str          # Pooled (asyncpg) — used by the app at runtime
    DIRECT_URL: str            # Direct (psycopg2) — used by Alembic migrations

    # External APIs
    OPEN_METEO_URL: str = "https://api.open-meteo.com"
    OSRM_URL: str = "http://router.project-osrm.org"  # used only for one-shot corridor geometry at seed time
    TAVILY_API_KEY: str = ""

    # Pipeline
    RISK_THRESHOLD: float = 0.65
    DEMO_MODE: bool = False
    SEED_BASELINE_DATA: bool = True
    RUN_PIPELINE_ON_STARTUP: bool = True
    PIPELINE_INTERVAL_MINUTES: int = 30
    RISK_SEGMENT_COUNT: int = 12

    # Realtime / national grid
    OPEN_METEO_GRID_STEP_DEG: float = 0.25
    REALTIME_RAIN_INTERVAL_MINUTES: int = 30
    LHASA_NRT_INTERVAL_MINUTES: int = 60
    ZONE_RISK_INTERVAL_HOURS: int = 6
    POIS_REFRESH_INTERVAL_DAYS: int = 7

    # Ecuador bounding box
    ECUADOR_BBOX_NORTH: float = 2.0
    ECUADOR_BBOX_SOUTH: float = -5.0
    ECUADOR_BBOX_WEST: float = -81.0
    ECUADOR_BBOX_EAST: float = -75.0

    # AI Agent
    ANTHROPIC_API_KEY: str = ""
    AGENT_WEB_SEARCH_MAX_PER_TURN: int = 3

    # Clerk auth
    CLERK_JWT_ISSUER: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_SECRET_KEY: str = ""

    # Kapso — WhatsApp chatbot
    KAPSO_API_KEY: str = ""
    KAPSO_PHONE_NUMBER_ID: str = ""

    # Twilio — SMS alerts
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM: str = ""

    @property
    def async_database_url(self) -> str:
        """Ensures the DATABASE_URL uses the asyncpg driver.
        Strips query params (e.g. ?pgbouncer=true) that asyncpg rejects.
        """
        url = self.DATABASE_URL
        # Remove query string — asyncpg doesn't accept URL-level params
        url = url.split("?")[0]
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def ecuador_bbox(self) -> tuple[float, float, float, float]:
        """Returns (west, south, east, north) for rasterio/osmnx."""
        return (
            self.ECUADOR_BBOX_WEST,
            self.ECUADOR_BBOX_SOUTH,
            self.ECUADOR_BBOX_EAST,
            self.ECUADOR_BBOX_NORTH,
        )


settings = Settings()
