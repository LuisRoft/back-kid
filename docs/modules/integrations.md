# Módulo: Integrations (`app/integrations/`)

## Qué hace

Clientes delgados para APIs y fuentes de datos externas. Sin lógica de negocio — solo fetching, parsing mínimo, y manejo de errores tipados. El pipeline los llama; los processors transforman lo que retornan.

## Estructura

```text
app/integrations/
├── open_meteo.py     # Precipitación forecast — REST, sin API key
├── nasa_lhasa.py     # Landslide hazard NetCDF — descarga diaria
├── osrm.py           # Ruteo vial — API pública, pre-computado
└── osmnx_client.py   # Red vial OSM — descarga para Ecuador
```

## Clientes

### `open_meteo.py`

- **Qué fetcha:** precipitación acumulada y probabilidad de lluvia extrema para Ecuador
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Auth:** ninguna — API pública gratuita
- **Bbox Ecuador:** lat -5°/2°, lon -81°/-75°
- **Retorna:** JSON con series temporales por punto de grilla

### `nasa_lhasa.py`

- **Qué fetcha:** NetCDF diario de probabilidad de deslizamiento (landslide nowcast)
- **Formato:** NetCDF — procesado por `netcdf_processor.py` en el pipeline
- **Auth:** ninguna — dataset público de NASA
- **Frecuencia:** una descarga por día (~50-100MB global, se recorta a Ecuador)

### `osrm.py`

- **Qué fetcha:** rutas alternativas entre dos puntos geográficos
- **Endpoint:** `http://router.project-osrm.org`
- **Auth:** ninguna — API pública
- **Uso:** solo en fase de pre-cómputo (no en cada request de usuario)
- **Retorna:** JSON con ruta, distancia y tiempo estimado

### `osmnx_client.py`

- **Qué fetcha:** red vial de Ecuador desde OpenStreetMap
- **Librería:** `osmnx` — descarga y parsea en una llamada
- **Uso:** solo en startup y refresco semanal
- **Retorna:** grafo de red vial cargado en PostGIS

## Reglas de capa

- Solo fetching y parsing de la respuesta cruda — sin lógica de negocio
- Errores de red o parsing → excepciones tipadas que el pipeline captura
- Sin estado interno — funciones puras o clases stateless
- Sin llamadas directas a DB — retornan datos crudos al pipeline

## Estado

- [ ] En construcción
