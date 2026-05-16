# Módulo: Pipeline (`app/pipeline/`)

## Qué hace

Ingesta y procesamiento de datos en background. Corre completamente desacoplado de la API — escribe en DB, nunca llama endpoints. Es el corazón del sistema: convierte datos satelitales y climáticos en forecasts de riesgo pre-computados.

## Estructura

```
app/pipeline/
├── scheduler.py           # APScheduler — registra y dispara las tareas
├── tasks/
│   ├── weather_ingest.py  # Fetcha Open-Meteo cada 6h
│   ├── lhasa_ingest.py    # Descarga NASA LHASA NetCDF cada 24h
│   ├── osm_ingest.py      # Carga red vial OSM (startup + semanal)
│   └── cascade_compute.py # Recomputa forecasts tras cada ingesta
└── processors/
    ├── netcdf_processor.py   # xarray + rasterio: clip LHASA a Ecuador bbox
    ├── geo_processor.py      # shapely + pyproj: intersecta raster con carreteras
    └── weather_processor.py  # Normaliza JSON de Open-Meteo a formato interno
```

## Schedule

| Tarea | Frecuencia | Qué hace |
|---|---|---|
| `weather_ingest` | Cada 6h | Fetcha precipitación forecast para Ecuador |
| `lhasa_ingest` | Cada 24h | Descarga NetCDF + corre `geo_processor` (paso CPU-heavy) |
| `cascade_compute` | Tras cada ingesta | Cruza datos y actualiza `risk_forecasts` en DB |
| `osm_ingest` | Startup + semanal | Carga red vial de Ecuador en PostGIS |

## Decisiones técnicas

**APScheduler in-process.** Corre dentro del proceso FastAPI. No requiere Redis, Celery ni workers separados. Suficiente para el volumen del MVP.

**CPU-bound en executor.** El paso geoespacial (`geo_processor`) usa `run_in_executor` para no bloquear el event loop de FastAPI durante los ~60-120s que tarda.

**Processors son funciones puras.** Reciben datos crudos, retornan datos procesados. Sin side effects — fáciles de testear y de encadenar.

**Tolerancia a fallos.** Si un run falla, APScheduler intenta en el siguiente ciclo. Los errores se loguean en `pipeline_runs` en DB.

## Fuentes de datos

| Processor | Fuente | Formato |
|---|---|---|
| `weather_processor` | Open-Meteo API | JSON REST |
| `netcdf_processor` | NASA LHASA | NetCDF (xarray + rasterio) |
| `geo_processor` | OSM via osmnx | GraphML / PostGIS |

## Estado

- [ ] En construcción
