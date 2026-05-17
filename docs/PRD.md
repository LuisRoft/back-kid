# PRD — back-kid (Backend)

**Proyecto:** Sistema ciudadano de gestión de riesgo catastrófico
**Track:** DEF/ACC — Hackathon Latam
**Scope del backend:** API + pipeline de datos satelitales + agente conversacional
**Arquitectura técnica:** Ver [architecture.md](./architecture.md)
**Change log del pivote:** Ver [changes/2026-05-17-citizen-pivot.md](./changes/2026-05-17-citizen-pivot.md)

---

## 1. Problema

Eventos catastróficos en Ecuador (deslaves, lluvias extremas, bloqueos viales rurales por lodo) afectan al ciudadano con horas o días de anticipación que hoy no se aprovechan. Existen pronósticos climáticos (NOAA, Open-Meteo) y datos de susceptibilidad de terreno (NASA LHASA), pero ningún sistema responde la pregunta que le importa al ciudadano:

> "¿Qué riesgo tengo en mi ubicación y qué hago al respecto?"

Sin esa respuesta accionable, el ciudadano queda reactivo: se entera del bloqueo cuando ya no le entra comida, medicina o transporte. El backend convierte señales climáticas y geofísicas en inteligencia personalizada — riesgo por zona + plan de acción generado por un agente conversacional.

---

## 2. Alcance MVP

- **Usuario:** ciudadano único (sin actores multi-rol).
- **País:** Ecuador.
- **Auth:** Clerk (frontend). Backend verifica JWT en endpoints del agente.
- **Perfil del ciudadano:** vive en Clerk `unsafeMetadata` (sin tabla `users` en MVP).
- **Geometría de riesgo:**
  - Corredores OSM (detección automática, igual que hoy).
  - **Zonas administrativas** (cantón/parroquia) con score de riesgo agregado.
- **Cobertura de fenómenos:** deslaves + lluvias extremas + inundaciones inferidas (precipitación acumulada).

---

## 3. Modos de operación

| Modo | Descripción |
|---|---|
| **Forecast** | Pipeline cada 30 min cruza Open-Meteo + NASA LHASA para producir riesgo por corredor y por zona en horizontes 24/48/72h. |
| **Tiempo real** | Snapshot de lluvia actual sobre grilla nacional (cada 30 min) + eventos LHASA near-real-time (cada hora). |
| **Demo histórico** | Datos del Niño 2023 en Ecuador pre-cargados. Disponible para demo cuando no hay actividad significativa en tiempo real. |

El frontend puede mostrar las capas que decida; el backend sirve los datasets independientes.

---

## 4. Funcionalidades del backend — MVP

### 4.1 Pipeline de ingesta

**F-01 — Ingesta meteorológica forecast (cada 30 min)**
Consume Open-Meteo para puntos de corredores activos y para una **grilla nacional de Ecuador** (default 0.25°, ~150 puntos). Extrae precipitación acumulada 24/48/72h y probabilidad de lluvia extrema.

**F-02 — Ingesta meteorológica realtime (cada 30 min)**
Consume Open-Meteo `current_weather` sobre la grilla nacional. Guarda muestras de precipitación actual en `realtime_rain_samples`.

**F-03 — Ingesta LHASA daily (cada 24h)**
Descarga NetCDF de NASA LHASA, recorta al bbox de Ecuador, convierte a susceptibilidad utilizable por el cómputo de cascada.

**F-04 — Ingesta LHASA near-real-time (cada 1h)**
Eventos LHASA recientes → `realtime_landslide_events`. Si no hay feed NRT, parsea el último NetCDF y diffeа contra la corrida previa.

**F-05 — Red vial OSM (startup + semanal)**
Descarga red vial Ecuador con osmnx, carga en PostGIS, calcula impacto poblacional por segmento.

**F-06 — POIs vía Overpass (startup + semanal)**
Llama Overpass API para Ecuador y upsertea en tabla `pois` los tipos: `hospital`, `clinic`, `pharmacy`, `supermarket`. **Albergues y ayuda humanitaria no se cargan en DB**; los gestiona el agente vía Tavily en demanda.

### 4.2 Modelo de cascada y zonas

**F-07 — Cascade compute por corredor (tras cada ingesta)**
Cruza precipitación + susceptibilidad por corredor → `risk_forecasts` y `risk_segments` por horizonte 24/48/72h. Si `probability > RISK_THRESHOLD` → genera `alert`.

**F-08 — Cómputo de riesgo por zona administrativa (tras F-07)**
Agrega precipitación + susceptibilidad por polígono administrativo (cantón/parroquia) → `zone_risk_forecasts`.

### 4.3 Perfil epidemiológico (uso interno del agente)

**F-09 — Contexto histórico de salud**
Datos PAHO/SIVIGILA pre-cargados por municipio (tabla `municipalities.epi_profile`). **No se mapean en frontend.** Lo usa el agente como contexto adicional cuando el ciudadano pregunta sobre kits, medicinas o riesgos de salud específicos de su zona.

### 4.4 API REST

Base path: `/api/v1`

**Mapa (públicos, sin auth):**

```
GET /map/corridors?bbox=
GET /map/risk-segments?horizon=24|48|72
GET /map/zones?bbox=&horizon=24|48|72
GET /map/rain/realtime?bbox=
GET /map/rain/forecast?bbox=&horizon=24|48|72
GET /map/landslides/realtime?bbox=&hours=24
GET /map/landslides/forecast?bbox=&horizon=24|48|72
GET /map/pois?bbox=&types=hospital,clinic,pharmacy,supermarket
```

**Alertas (públicas):**

```
GET /alerts
GET /alerts/corridor/{corridor_id}
```

**Pipeline (público, debug):**

```
GET /pipeline/runs?limit=50
```

**Agente (privado — requiere `Authorization: Bearer <clerk_jwt>`):**

```
POST /agent/chat
   body: { message: str, session_id?: str }
   response: SSE stream { type, text, session_id }
```

El backend extrae el perfil del ciudadano del JWT (`unsafe_metadata` como custom claim) y lo inyecta como contexto fijo del agente — el frontend no envía el perfil en el body.

### 4.5 Agente conversacional (Claude Agent SDK)

In-process MCP server (`create_sdk_mcp_server("hermes", ...)`) con tools:

| Tool | Función |
|---|---|
| `get_my_risk(lat, lon)` | Riesgo de la zona del ciudadano: lluvia 24/48/72h + landslide forecast + eventos reales recientes |
| `get_realtime_rain(lat, lon, radius_km)` | Muestras de lluvia actual en radio |
| `get_nearby_pois(lat, lon, types[], k=5)` | POIs cercanos de la tabla `pois` |
| `web_search(query)` | Tavily Search — para info temporal/no estructurada (albergues, ayuda humanitaria activa, noticias locales). Cuota máx 3 búsquedas por turno |
| `get_active_alerts()` | Alertas activas (≥ RISK_THRESHOLD) |
| `get_local_health_context(lat, lon)` | Perfil epidemiológico histórico de municipios cercanos (uso interno del LLM) |

**Sesión:** `resume=session_id` built-in del SDK. Sin persistencia cross-session en MVP.

**Modo:** reactivo. Sin notificaciones push ni planes proactivos.

---

## 5. Funcionalidades pendientes (post-MVP)

**P-01 — Notificaciones proactivas**
Cuando el sistema detecta alto riesgo en la zona del ciudadano (forecast + ubicación del perfil), genera y entrega un plan automático. Requiere tabla `users` (persistencia server-side) y un canal de entrega (push, email, webhook).

**P-02 — Seguimiento post-evento**
Validar si el cierre/deslave predicho efectivamente ocurrió (`actual_outcome` en `alerts`).

**P-03 — Government action broadcast**
Feed público de acciones tomadas por autoridades (pre-posicionamiento, cierres, envío de insumos). Visible para todos los ciudadanos.

**P-04 — Expansión geográfica**
Colombia, Perú, Bolivia. Parametrizar pipeline por bbox + fuentes epidemiológicas locales.

**P-05 — Cards estructuradas del agente**
Que las respuestas del agente puedan incluir suggestions estructuradas (ej. "ir a este POI", "abrir capa X en el mapa") consumibles como UI cards en el frontend.

---

## 6. Modelo de datos (resumen)

| Tabla | Contenido |
|---|---|
| `corridors` | Segmentos de carretera con geometría PostGIS e impacto poblacional |
| `risk_forecasts` | Probabilidad por corredor × horizonte (24/48/72h) × timestamp |
| `risk_segments` | Tramos específicos con riesgo + geometría propia |
| `zones` | Cantones/parroquias de Ecuador (seed INEC) |
| `zone_risk_forecasts` | Score de riesgo por zona × horizonte |
| `realtime_rain_samples` | Muestras de lluvia actual por punto de grilla × timestamp |
| `realtime_landslide_events` | Eventos LHASA NRT |
| `pois` | Hospitales, clínicas, farmacias, supermercados (fuente OSM Overpass) |
| `municipalities` | Geometría + perfil epidemiológico histórico (uso interno del agente) |
| `alerts` | Alertas generadas cuando probability > threshold |
| `pipeline_runs` | Log de ejecución de cada tarea |

**Eliminada en el pivote:** `rerouting_plans`.

---

## 7. Fuentes de datos

| Dataset | Fuente | Frecuencia |
|---|---|---|
| Precipitación forecast | Open-Meteo API | 30 min |
| Precipitación actual | Open-Meteo `current_weather` | 30 min |
| Landslide susceptibility | NASA LHASA daily NetCDF | 24h |
| Landslide events NRT | NASA LHASA NRT | 1h |
| Red vial | OpenStreetMap via osmnx | Startup + semanal |
| POIs (hospitales, farmacias, supermercados) | OSM Overpass API | Startup + semanal |
| Perfil epidemiológico | PAHO / SIVIGILA (CSV) | Pre-cargado |
| Población por zona | CEPAL / INEC Ecuador | Pre-cargado |
| Zonas administrativas | INEC GeoJSON oficial | Seed estático |
| Búsqueda web para agente | Tavily Search API | En demanda |
| Demo histórico | El Niño 2023 Ecuador | Seed estático |

Fuentes públicas y gratuitas excepto **Tavily**, que requiere `TAVILY_API_KEY` y se usa solo desde el agente con cuota por turno.

---

## 8. Requisitos no funcionales

- Latencia API mapa: < 200ms por endpoint (datos pre-computados, no cálculo on-demand).
- Pipeline tolerante a fallos: si un run falla, el siguiente ciclo reintenta.
- Pasos CPU-bound del pipeline: `run_in_executor` para no bloquear el event loop.
- Configuración tipada en `app/config.py` via pydantic-settings.
- Verificación de JWT Clerk con caché de JWKS en memoria (TTL 1h).
- Sin secrets en código.

---

## 9. Deployment

| Servicio | Plataforma |
|---|---|
| Backend (FastAPI + pipeline) | Railway |
| Base de datos | Supabase (PostgreSQL + PostGIS) |
| Frontend | Vercel |

---

## 10. Out of scope (MVP)

- Roles de usuario multi-actor (gobierno / logística / salud).
- Notificaciones push / proactivas del agente.
- Dashboards por actor (eliminados en el pivote).
- Cálculo de rutas alternativas (OSRM eliminado).
- Mapeo de epidemiología en el frontend (datos sólo como contexto interno del agente).
- Mapeo de albergues / ONGs en el mapa (los resuelve el agente vía Tavily).
- Persistencia del perfil del ciudadano en backend (vive en Clerk `unsafeMetadata`).
- Cobertura fuera de Ecuador.
- Interfaz de administración.
