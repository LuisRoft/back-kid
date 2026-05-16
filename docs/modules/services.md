# Módulo: Services (`app/services/`)

## Qué hace

Lógica de negocio del sistema. Capa intermedia entre los routers (HTTP) y los repositories (DB). Todo el razonamiento sobre los datos vive aquí — el cascade model, la generación de alertas, los planes de rerouting.

## Estructura

```
app/services/
├── cascade_service.py   # Modelo de cascada: cruza weather + LHASA + roads
├── alert_service.py     # Evalúa umbrales, genera y persiste alertas
├── routing_service.py   # Construye planes de rerouting para logística
└── forecast_service.py  # Agrega forecasts 24/48/72h para respuestas de API
```

## Responsabilidades por servicio

### `cascade_service.py`
- Recibe datos de precipitación y susceptibilidad de deslave
- Calcula probabilidad de cierre por corredor × horizonte (24/48/72h)
- Llama a `alert_service` si la probabilidad supera el threshold
- Escribe resultados en `risk_forecasts` via repository

### `alert_service.py`
- Evalúa si `risk_forecast.probability > RISK_THRESHOLD`
- Genera el objeto `Alert` con paquetes de inteligencia por actor
- Persiste en DB via `alert_repo`
- Nunca duplica alertas activas para el mismo corredor

### `routing_service.py`
- Recibe un `corridor_id` en riesgo
- Consulta `rerouting_plans` pre-computados en DB
- Si no existe plan pre-computado, dispara cálculo via `osrm` integration
- Retorna `ReroutingPlan` con rutas alternativas y tiempos estimados

### `forecast_service.py`
- Agrega `risk_forecasts` de DB en la forma que espera cada dashboard
- Para Gobierno: ordena por `population_impact` desc
- Para Salud: filtra corredores que aislan municipios con riesgo epidemiológico
- Para Logística: filtra por corredor específico o todos

## Reglas de capa

- Sin imports de FastAPI — puro Python
- Sin queries SQL directas — solo llamadas a repositories
- Retornan Pydantic schemas o dicts, nunca modelos ORM directamente
- Totalmente unit-testeables sin servidor ni DB (repositories mockeables)

## Estado

- [ ] En construcción
