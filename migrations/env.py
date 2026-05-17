from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

import geoalchemy2  # noqa: F401 — registers PostGIS types with Alembic

from app.config import settings
from app.models.base import Base  # noqa: F401
from app.models import (  # noqa: F401
    Alert,
    Corridor,
    Municipality,
    PipelineRun,
    Poi,
    RealtimeLandslideEvent,
    RealtimeRainSample,
    RiskForecast,
    RiskSegment,
    Zone,
    ZoneRiskForecast,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use DIRECT_URL (non-pooled, port 5432) with psycopg2 sync driver for DDL
config.set_main_option(
    "sqlalchemy.url",
    settings.DIRECT_URL.replace("postgresql://", "postgresql+psycopg2://", 1),
)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
