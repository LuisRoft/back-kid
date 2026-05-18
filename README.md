# back-kid — Backend Aegis

**Sistema de alerta temprana para infraestructura crítica — Hackathon Latam (Track DEF/ACC)**

Convierte señales climáticas y geofísicas (NASA LHASA + Open-Meteo) en inteligencia accionable con **24-72 horas de anticipación** para el ciudadano.

---

## Qué hace

- **Pipeline en background** ingesta datos satelitales y climáticos cada 30 min
- **Pre-computa forecasts de riesgo** por corredor vial y zona administrativa
- **Sirve API REST** con capas GeoJSON para el mapa y endpoints para el agente conversacional
- **Agente Hermes** (Claude Agent SDK) genera planes de acción personalizados

---

## Stack

| Capa | Tecnología |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI async |
| ORM | SQLAlchemy 2.0 async + **GeoAlchemy2** |
| Database | **PostgreSQL + PostGIS** (Supabase) |
| Migrations | Alembic + GeoAlchemy2 |
| Scheduler | APScheduler (in-process) |
| Config | pydantic-settings |
| Package manager | **uv** |

---

## Arquitectura

```
app/
├── main.py               # App factory — lifespan con scheduler
├── config.py             # pydantic-settings — todas las env vars tipadas
├── dependencies.py       # FastAPI dependencies compartidas
│
├── api/v1/               # Routers HTTP — solo HTTP, sin lógica de negocio
│   ├── map.py           # /map/* — capas GeoJSON
│   ├── alerts.py        # /alerts/*
│   ├── forecasts.py     # /forecasts/*
│   ├── pipeline.py      # /pipeline/runs (debug)
│   └── webhooks.py      # webhooks externos
│
├── services/             # Lógica de negocio — Python puro, sin FastAPI
│   ├── cascade_service.py   # Cruza precipitación × susceptibilidad
│   ├── alert_service.py    # Evalúa thresholds, genera alertas
│   └── forecast_service.py  # Agrega datos 24/48/72h para la API
│
├── pipeline/             # Background — se ejecuta cada 30 min
│   ├── scheduler.py     # APScheduler — registra y dispara tasks
│   ├── tasks/
│   │   ├── realtime_rain_task.py    # Open-Meteo actual (cada 30 min)
│   │   ├── weather_task.py           # Open-Meteo forecast (cada 6h)
│   │   ├── lhasa_realtime_task.py   # NASA LHASA NRT (cada 1h)
│   │   ├── pois_task.py             # OSM Overpass POIs (startup + semanal)
│   │   ├── risk_task.py             # Computa risk_segments
│   │   ├── zone_risk_task.py        # Agrega riesgo por zona administrativa
│   │   └── seed_demo.py             # Seed histórico El Niño 2023
│   └── processors/
│       ├── susceptibility.py  # NASA LHASA GeoTIFF — sampling por punto
│       ├── risk_scorer.py     # Fórmulas de probabilidad
│       ├── zone_aggregator.py # Agregación por polígono administrativo
│       └── constants.py      # Thresholds y pesos LHASA
│
├── models/               # SQLAlchemy ORM — schema de la DB
├── schemas/               # Pydantic v2 — request/response shapes
├── db/
│   ├── session.py        # AsyncEngine + AsyncSessionLocal
│   └── repositories/      # Todas las queries SQL — services usan repos, no models
│
└── integrations/         # Clientes HTTP — sin lógica de negocio
    ├── open_meteo.py      # Precipitación forecast + actual
    ├── nasa_lhasa.py     # NetCDF download
    └── osmnx_client.py  # OSM road network
```

---

## Fórmula de Riesgo (el corazón)

```
P(cierre) = score_precipitación × peso_LHASA

score_precipitación = min(0.05 + 0.65 × (mm / umbral), 0.95)

Umbrales Ecuador (IDEAM):
  24h → 50mm   |  48h → 100mm  |  72h → 150mm

Pesos susceptibilidad LHASA (clase 0–5):
  Clase 0 (agua): 0.00    Clase 3 (moderada): 0.70
  Clase 1 (muy baja): 0.05  Clase 4 (alta): 0.85
  Clase 2 (baja): 0.30    Clase 5 (muy alta): 1.00
```

**Calibración:** La clase 3 alcanza max 0.665 (> threshold 0.65) con lluvia extrema. Clases 1-2 nunca alertan en el MVP.

---

## Modelo de Datos

| Tabla | Descripción |
|---|---|
| `corridors` | Segmentos de carretera con geometría PostGIS + impacto poblacional |
| `risk_forecasts` | Probabilidad por corredor × horizonte × timestamp |
| `risk_segments` | Tramos específicos con riesgo > threshold — layer rojo/naranja del mapa |
| `zones` | Cantones/parroquias con score agregado |
| `municipalities` | Geometría + perfil эпидемиológico PAHO/SIVIGILA (contexto interno del agente) |
| `realtime_rain_samples` | Lluvia actual por punto de grilla |
| `realtime_landslide_events` | Eventos LHASA NRT |
| `pois` | Hospitales, farmacias, supermercados (OSM Overpass) |
| `alerts` | Generadas cuando probability > 0.65 |

---

## Fuentes de Datos

| Dataset | Fuente | Frecuencia |
|---|---|---|
| Precipitación forecast | Open-Meteo API | 30 min |
| Lluvia actual | Open-Meteo `current_weather` | 30 min |
| Susceptibilidad deslaves | NASA LHASA NetCDF | 24h |
| Deslaves NRT | NASA LHASA | 1h |
| Red vial | OSM via osmnx | Startup + semanal |
| POIs | OSM Overpass API | Startup + semanal |
| Perfil epidemiológico | PAHO / SIVIGILA | Pre-cargado |
| Demo histórico | El Niño 2023 Ecuador | Seed estático |

Todas las fuentes son **públicas y gratuitas** excepto Tavily (usado solo por Hermes).

---

## API Endpoints

```
GET  /api/v1/map/corridors              → GeoJSON corredores monitoreados
GET  /api/v1/map/risk-segments?horizon=24|48|72  → Tramos con riesgo activo
GET  /api/v1/map/zones?horizon=24|48|72         → Zonas administrativas
GET  /api/v1/map/rain/realtime         → Heatmap lluvia actual
GET  /api/v1/map/rain/forecast?horizon=          → Pronóstico precipitación
GET  /api/v1/map/landslides/realtime   → Eventos deslave recientes
GET  /api/v1/map/pois                 → Recursos ciudadanos
GET  /api/v1/alerts                    → Alertas activas
GET  /api/v1/alerts/{corridor_id}      → Alertas por corredor
GET  /api/v1/pipeline/runs             → Log de ejecuciones
POST /api/v1/agent/chat               → Hermes (SSE, requiere Clerk JWT)
GET  /health                           → Health check
```

---

## Reglas de Arquitectura

- **API layer** → solo HTTP: parsing, serialización, status codes. Sin lógica de negocio.
- **Services** → Python puro. Sin imports de FastAPI. Unit-testables sin servidor.
- **Repositories** → Toda la SQL. Services llaman repos, nunca models directamente.
- **Pipeline** → Desacoplado de la API. Corre cada 30 min via APScheduler, escribe directo a DB. CPU-bound usa `run_in_executor`.
- **Integrations** → Clientes HTTP thin. Sin lógica de negocio. Excepciones tipadas que los services manejan.

---

## Lo que demuestra ingeniería

1. **Arquitectura en capas clara** — API → Services → Repositories → DB. Sin negocio en routers.
2. **Pipeline desacoplado** — APScheduler in-process, sin Redis/Celery. Si falla, el siguiente ciclo reintenta.
3. **Geoespacial nativo** — PostGIS para geometrías, rasterio + xarray para NetCDF LHASA.
4. **Pre-computación** — Latencia < 200ms. Todo viene de DB pre-computado, no cálculo on-demand.
5. **Fórmulas calibradas** — Thresholds basados en literatura científica (IDEAM). Pesos LHASA matemáticamente calibrados para threshold 0.65.
6. **Type safety completo** — Pydantic v2 schemas, SQLAlchemy 2.0 typed, pydantic-settings.
7. **Async end-to-end** — asyncpg, AsyncSession, todas las operaciones de DB son non-blocking.
8. **Config tipada** — Todas las env vars en `config.py`, validadas al startup.

---

## Quickstart

```bash
# Instalar dependencias
uv sync

# Configurar variables
cp .env.example .env
# Editar .env con DATABASE_URL

# Correr en desarrollo
uv run fastapi dev app/main.py
```

---

## Deployment

| Componente | Plataforma |
|---|---|
| Backend (FastAPI + pipeline) | **Railway** |
| Database | **Supabase** (PostgreSQL + PostGIS) |

---

## Documentación

| Documento | Descripción |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product Requirements — problema, alcance, features |
| [docs/architecture.md](docs/architecture.md) | Arquitectura completa — capas, schedule, decisiones |
| [docs/modules/pipeline.md](docs/modules/pipeline.md) | Pipeline — tasks, processors, schedule |
| [docs/modules/db.md](docs/modules/db.md) | DB — modelos, repositories, migrations |
| [docs/modules/api.md](docs/modules/api.md) | API — endpoints, versioning |