# Módulo: DB (`app/db/` + `app/models/`)

## Qué hace

Gestión de la base de datos. Incluye la sesión async de SQLAlchemy, los modelos ORM con soporte geoespacial (GeoAlchemy2), y el patrón repository que encapsula todas las queries.

## Estructura

```
app/
├── models/
│   ├── base.py                  # DeclarativeBase compartida
│   ├── corridor.py              # Segmentos de carretera con geometría PostGIS
│   ├── risk_forecast.py         # Probabilidades por corredor × horizonte × timestamp
│   ├── municipality.py          # Geometría + perfil epidemiológico PAHO
│   └── alert.py                 # Alertas generadas cuando probability > threshold
│
└── db/
    ├── session.py               # Engine async + AsyncSessionLocal factory
    └── repositories/
        ├── corridor_repo.py     # CRUD + queries geoespaciales de corredores
        ├── forecast_repo.py     # Lectura de forecasts por horizonte y threshold
        ├── municipality_repo.py # Municipios en riesgo de aislamiento
        └── alert_repo.py        # Alertas activas, deduplicación, historial
```

## Modelos ORM

### `Corridor`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `name` | str | Nombre del corredor (ej: "Quito-Guayaquil") |
| `geometry` | Geometry(LineString) | Trazado con PostGIS |
| `population_impact` | int | Personas que dependen de esta ruta |
| `country` | str | "EC" para Ecuador |

### `RiskForecast`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `corridor_id` | UUID | FK → Corridor |
| `horizon_hours` | int | 24, 48 o 72 |
| `probability` | float | 0.0 a 1.0 |
| `computed_at` | datetime | Timestamp del pipeline run |
| `is_demo` | bool | True si viene del seed histórico |

### `Municipality`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `name` | str | Nombre del municipio |
| `geometry` | Geometry(Polygon) | Área con PostGIS |
| `epi_profile` | JSONB | Historial PAHO: dengue, cólera, resp. por evento El Niño |

### `Alert`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | PK |
| `corridor_id` | UUID | FK → Corridor |
| `probability` | float | Probabilidad que disparó la alerta |
| `horizon_hours` | int | Horizonte del forecast |
| `generated_at` | datetime | Cuándo se generó |
| `is_active` | bool | False cuando el evento pasa |

## Patrón Repository

Todas las queries SQL viven en repositories. Los services nunca escriben SQL directamente.

```python
# Correcto — service llama repo
corridors = await corridor_repo.get_high_risk(session, min_probability=0.65)

# Incorrecto — service no hace queries directas
corridors = await session.execute(select(Corridor).where(...))
```

## Migrations

Manejadas con Alembic. Soporte PostGIS incluido via GeoAlchemy2.

```bash
# Crear nueva migración
uv run alembic revision --autogenerate -m "descripcion"

# Aplicar migrations
uv run alembic upgrade head
```

## Estado

- [ ] En construcción
