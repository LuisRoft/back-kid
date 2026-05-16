# Architecture — back-kid

## Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) + GeoAlchemy2 |
| Migrations | Alembic |
| Database | PostgreSQL + PostGIS (Supabase) |
| Scheduler | APScheduler (inside FastAPI process) |
| Config | pydantic-settings |
| Package manager | uv |

---

## Folder Structure

```
back-kid/
├── app/
│   ├── main.py                     # App factory — creates FastAPI instance, registers routers, starts scheduler
│   ├── config.py                   # pydantic-settings — all env vars typed here
│   ├── dependencies.py             # Shared FastAPI dependencies (DB session, etc.)
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # Aggregates all v1 routers under /api/v1
│   │       ├── government.py       # GET /api/v1/dashboard/government
│   │       ├── logistics.py        # GET /api/v1/dashboard/logistics
│   │       └── health.py           # GET /api/v1/dashboard/health
│   │
│   ├── services/                   # Business logic — pure Python, no FastAPI imports
│   │   ├── cascade_service.py      # Cascade model: crosses weather + LHASA + roads
│   │   ├── alert_service.py        # Evaluates thresholds, generates alerts
│   │   ├── routing_service.py      # Rerouting plans via OSRM
│   │   └── forecast_service.py     # Aggregates 24/48/72h forecast data for API
│   │
│   ├── pipeline/                   # Background ingestion and processing
│   │   ├── scheduler.py            # APScheduler setup — registers all tasks
│   │   ├── tasks/
│   │   │   ├── weather_ingest.py   # Runs every 6h — fetches Open-Meteo
│   │   │   ├── lhasa_ingest.py     # Runs every 24h — downloads NASA LHASA NetCDF
│   │   │   ├── osm_ingest.py       # Runs once at startup + weekly — loads OSM road network
│   │   │   └── cascade_compute.py  # Runs after each ingest — recomputes cascade model
│   │   └── processors/
│   │       ├── netcdf_processor.py # xarray + rasterio: clips LHASA NetCDF to Ecuador bbox
│   │       ├── geo_processor.py    # shapely + pyproj: intersects raster cells with road geometries
│   │       └── weather_processor.py# Normalizes Open-Meteo JSON to internal format
│   │
│   ├── models/                     # SQLAlchemy ORM models (DB schema)
│   │   ├── base.py                 # DeclarativeBase
│   │   ├── corridor.py             # Road corridors with PostGIS geometry
│   │   ├── risk_forecast.py        # Risk predictions per corridor per horizon (24/48/72h)
│   │   ├── municipality.py         # Municipality geometries + epidemiological profile
│   │   └── alert.py                # Generated alerts when threshold is crossed
│   │
│   ├── schemas/                    # Pydantic v2 schemas — API request/response shapes
│   │   ├── common.py               # Shared types (GeoJSON wrappers, pagination, etc.)
│   │   ├── government.py           # PrioritizedRiskList, CorridorRiskItem
│   │   ├── logistics.py            # ReroutingPlan, AlternativeRoute
│   │   └── health.py               # MunicipalityRiskMap, EpidemiologicalProfile
│   │
│   ├── db/
│   │   ├── session.py              # Async SQLAlchemy engine + session factory
│   │   └── repositories/           # All DB queries live here — services call repos, not models directly
│   │       ├── corridor_repo.py
│   │       ├── forecast_repo.py
│   │       ├── municipality_repo.py
│   │       └── alert_repo.py
│   │
│   └── integrations/               # Thin clients for external APIs
│       ├── open_meteo.py           # Precipitation forecast — no API key, REST
│       ├── nasa_lhasa.py           # Landslide hazard NetCDF download
│       ├── osrm.py                 # Route calculation — public API, pre-computed
│       └── osmnx_client.py         # OSM road network download for Ecuador
│
├── data/
│   ├── seed/                       # El Niño 2023 historical data (demo mode)
│   └── cache/                      # Downloaded NetCDF files — gitignored
│
├── migrations/                     # Alembic migration files
│   └── versions/
│
├── tests/
│   ├── unit/                       # Pure logic tests — no DB, no HTTP
│   ├── integration/                # Tests that hit the DB or external APIs
│   └── conftest.py
│
├── scripts/
│   ├── seed_historical.py          # Loads El Niño 2023 data into DB for demo mode
│   └── load_osm.py                 # One-time OSM road network load for Ecuador
│
├── .env.example
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

---

## Layer Rules

### API layer (`app/api/`)
- Handles HTTP only: request parsing, response serialization, status codes
- No business logic — delegates everything to services
- No direct DB access — only through dependencies

### Service layer (`app/services/`)
- Pure Python — no FastAPI imports, no HTTP concepts
- Receives data, applies logic, returns results
- Calls repositories for DB access, never models directly
- Fully unit-testable without a running server

### Repository layer (`app/db/repositories/`)
- All SQL lives here — services never write queries
- Returns domain objects (SQLAlchemy models or Pydantic schemas)
- One repository per model/domain entity

### Pipeline (`app/pipeline/`)
- Completely decoupled from the API — writes to DB, never calls endpoints
- Tasks run on schedule via APScheduler, CPU-bound steps use `run_in_executor`
- Processors are pure functions: receive raw data, return processed data

### Integrations (`app/integrations/`)
- Thin HTTP clients — no business logic
- One file per external service
- Raise typed exceptions that services handle

---

## Schedule

| Task | Frequency | Why |
|---|---|---|
| `weather_ingest` | Every 6h | Open-Meteo updates precipitation forecasts every 6h |
| `lhasa_ingest` + `geo_processor` | Every 24h | NASA LHASA updates daily — heaviest CPU step |
| `cascade_compute` | After each ingest | Recomputes risk forecasts for all corridors |
| `osm_ingest` | Startup + weekly | Road network rarely changes |

---

## Database Schema (high level)

```
corridors           — road segments with PostGIS geometry, Ecuador only
risk_forecasts      — probability of closure per corridor × horizon (24/48/72h)
municipalities      — geometry + PAHO historical epidemiological profile
alerts              — generated when risk_forecast.probability > threshold
rerouting_plans     — pre-computed alternative routes per corridor (via OSRM)
```

---

## Environment Variables

Defined and typed in `app/config.py` via pydantic-settings. All required at startup.

```
DATABASE_URL        — Supabase PostgreSQL connection string (asyncpg driver)
OPEN_METEO_URL      — Base URL (https://api.open-meteo.com)
NASA_LHASA_URL      — LHASA NetCDF download endpoint
OSRM_URL            — OSRM routing API base URL
RISK_THRESHOLD      — Probability threshold to generate an alert (default: 0.65)
DEMO_MODE           — "true" to serve El Niño 2023 seed data alongside live data
```

---

## Key Decisions

**No Celery.** APScheduler with `run_in_executor` for CPU-bound steps is sufficient. The heavy geo processing runs once per 24h, not per request.

**No direct Supabase client.** The backend talks to PostgreSQL via SQLAlchemy + asyncpg. Supabase is the host, not a dependency.

**API versioning from day 1.** All endpoints live under `/api/v1/`. Allows breaking changes without affecting existing clients.

**Pre-computed forecasts.** The API never triggers the pipeline. It only reads pre-computed results from DB. This keeps latency under 100ms regardless of data complexity.

**Repository pattern.** Keeps services testable without a DB. Repositories can be mocked independently.
