FROM python:3.13-slim

WORKDIR /app

# System libraries required by rasterio (GDAL), shapely (GEOS) and pyproj (PROJ)
# slim does not ship these — they are not bundled in the Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libgeos-c1v5 \
    libproj25 \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Lock + manifest first so dependency layer is cached unless they change.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Application code.
COPY app/ ./app/

# Static data needed at runtime: LHASA susceptibility raster (~32 MB) and
# GeoJSON seeds (cantones, parroquias). Without these the pipeline runs in
# degraded mode and the seed task no-ops.
COPY data/ ./data/

# Alembic migrations + config (allow running `uv run alembic upgrade head`
# against the deployed image if ever needed).
COPY migrations/ ./migrations/
COPY alembic.ini ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
