from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — Supabase
    DATABASE_URL: str          # Pooled (asyncpg) — used by the app at runtime
    DIRECT_URL: str            # Direct (psycopg2) — used by Alembic migrations

    # External APIs
    OPEN_METEO_URL: str = "https://api.open-meteo.com"
    OSRM_URL: str = "http://router.project-osrm.org"

    # Pipeline
    RISK_THRESHOLD: float = 0.65
    DEMO_MODE: bool = False

    # Ecuador bounding box
    ECUADOR_BBOX_NORTH: float = 2.0
    ECUADOR_BBOX_SOUTH: float = -5.0
    ECUADOR_BBOX_WEST: float = -81.0
    ECUADOR_BBOX_EAST: float = -75.0

    # AI Agent (post-MVP)
    ANTHROPIC_API_KEY: str = ""

    @property
    def async_database_url(self) -> str:
        """Ensures the DATABASE_URL uses the asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
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
