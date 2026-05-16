# back-kid

Backend del sistema de alerta temprana para protección de infraestructura crítica — Hackathon Latam (Track DEF/ACC).

Convierte señales climáticas (NASA LHASA + Open-Meteo) en inteligencia accionable con 24-72 horas de anticipación para tres actores: Gobierno, Logística y Salud.

---

## Stack

| | |
|---|---|
| Runtime | Python 3.13 |
| Framework | FastAPI (async) |
| Database | PostgreSQL + PostGIS (Supabase) |
| ORM | SQLAlchemy 2.0 async + GeoAlchemy2 |
| Scheduler | APScheduler (in-process) |
| Package manager | uv |

---

## Documentación

| Documento | Descripción |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product Requirements — qué construimos y por qué |
| [docs/architecture.md](docs/architecture.md) | Arquitectura técnica — estructura, capas y decisiones |
| [docs/modules/api.md](docs/modules/api.md) | Módulo API — endpoints, routers, versioning |
| [docs/modules/pipeline.md](docs/modules/pipeline.md) | Módulo Pipeline — ingesta, procesamiento, scheduler |
| [docs/modules/services.md](docs/modules/services.md) | Módulo Services — lógica de negocio, cascade model |
| [docs/modules/db.md](docs/modules/db.md) | Módulo DB — modelos ORM, repositories, migrations |
| [docs/modules/integrations.md](docs/modules/integrations.md) | Módulo Integrations — clientes externos (LHASA, OSRM, OSM) |
| [docs/modules/agent.md](docs/modules/agent.md) | Módulo Agent — chatbot IA post-MVP (Claude Agent SDK) |

---

## Quickstart

```bash
# Instalar dependencias
uv sync

# Configurar variables de entorno
cp .env.example .env
# Editar .env con DATABASE_URL y demás

# Correr en desarrollo
uv run fastapi dev app/main.py
```

---

## Estructura

```
app/
├── main.py           # App factory
├── config.py         # Env vars tipadas (pydantic-settings)
├── api/v1/           # Routers HTTP
├── services/         # Lógica de negocio
├── pipeline/         # Ingesta y procesamiento en background
├── models/           # SQLAlchemy ORM
├── schemas/          # Pydantic schemas (API)
├── db/               # Session + repositories
└── integrations/     # Clientes externos
docs/                 # Documentación completa
data/seed/            # Datos históricos El Niño 2023 (demo mode)
migrations/           # Alembic
scripts/              # One-off scripts (seed, load OSM)
```
