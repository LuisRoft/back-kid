# Módulo: API (`app/api/`)

## Qué hace

Capa HTTP del sistema. Recibe requests, los delega a services, y serializa las respuestas. No contiene lógica de negocio.

## Estructura

```
app/api/
└── v1/
    ├── router.py        # Agrega todos los routers bajo /api/v1
    ├── government.py    # GET /api/v1/dashboard/government
    ├── logistics.py     # GET /api/v1/dashboard/logistics[/{corridor_id}]
    └── health.py        # GET /api/v1/dashboard/health
```

## Endpoints

| Método | Path | Actor | Descripción |
|---|---|---|---|
| GET | `/api/v1/dashboard/government` | Gobierno | Lista priorizada de corredores por impacto poblacional |
| GET | `/api/v1/dashboard/logistics` | Logística | Todos los corredores con plan de rerouting |
| GET | `/api/v1/dashboard/logistics/{corridor_id}` | Logística | Plan de rerouting de un corredor específico |
| GET | `/api/v1/dashboard/health` | Salud | Municipios en riesgo con perfil epidemiológico |
| GET | `/api/v1/alerts` | Todos | Alertas activas en este momento |
| GET | `/api/v1/alerts/{alert_id}` | Todos | Detalle de una alerta específica |
| GET | `/api/v1/map/corridors` | Mapa | Red de corredores monitoreados |
| GET | `/api/v1/map/risk-segments` | Mapa | Tramos específicos en riesgo, filtrables por probabilidad |
| GET | `/api/v1/map/rerouting-plans` | Mapa | Rutas alternas para corredores con alerta |
| GET | `/api/v1/pipeline/status` | Interno | Estado de cada tarea del pipeline |

## Reglas de capa

- Los routers importan services, nunca modelos ORM ni repos directamente
- Toda la lógica de negocio vive en `app/services/`
- Los schemas de request/response están en `app/schemas/`
- Sin lógica condicional compleja — si hay más de 3 líneas de lógica en un router, va a un service

## Schemas relacionados

- `app/schemas/government.py` → `PrioritizedRiskList`, `CorridorRiskItem`
- `app/schemas/logistics.py` → `ReroutingPlan`, `AlternativeRoute`
- `app/schemas/health.py` → `MunicipalityRiskMap`, `EpidemiologicalProfile`
- `app/schemas/common.py` → tipos compartidos, GeoJSON wrappers

## Estado

- [ ] En construcción
