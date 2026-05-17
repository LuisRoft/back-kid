# Change: Pivote a enfoque ciudadano + agente generador de planes de acción

**Fecha:** 2026-05-17
**Estado:** Propuesta — pendiente de plan de ejecución
**Afecta:** PRD, arquitectura del agente, modelo de datos (parcial), pipeline (parcial), frontend (fuera de este repo)

---

## 1. Motivación

El proyecto deja de ser una plataforma multi-actor (gobierno / logística / salud) enfocada en gestión de logística e infraestructura, y se reorienta **completamente al ciudadano** como usuario final. La pregunta que el sistema responde cambia de:

> "¿Qué corredores cerrarán y cómo redirigimos camiones?"

a:

> "¿Qué riesgo tengo en mi ubicación y qué hago al respecto?"

El motor sigue siendo predictivo (forecasts 24/48/72h) pero se complementa con una capa **en tiempo real** (qué está pasando ahora) y un **agente conversacional reactivo** que arma un plan de acción personalizado para el ciudadano.

---

## 2. Cambios de scope

### 2.1 Lo que entra (NUEVO)

| ID | Cambio |
|---|---|
| C-01 | Foco único: **ciudadano**. Eliminamos actores gobierno/logística/salud del frontend. |
| C-02 | **Agente conversacional reactivo** como funcionalidad core (no post-MVP). Genera planes de acción personalizados. |
| C-03 | Integración de **Tavily Search API** como tool del agente para buscar ayuda humanitaria, recursos, organizaciones y noticias locales en vivo. |
| C-04 | Capa **en tiempo real** en el mapa: lluvia ahora + deslaves reportados ahora (NASA LHASA near-real-time). |
| C-05 | **Heatmap nacional de lluvia** (Ecuador completo) — tanto predictivo como en tiempo real, no solo en corredores. |
| C-06 | **Riesgo por zonas administrativas** (cantón/parroquia) además de corredores. El ciudadano no necesariamente está sobre una carretera. |
| C-07 | Mostrar en mapa **POIs útiles al ciudadano** desde DB (Overpass/OSM): hospitales/clínicas, farmacias, tiendas/supermercados. **Albergues y ayuda humanitaria NO viven en DB en MVP** — los gestiona el agente vía Tavily porque OSM está flojo en esa categoría para Ecuador y la info es temporal (cambia por evento). |
| C-08 | El agente recibe inputs del ciudadano: **ubicación + perfil básico (familia, niños, adultos mayores, condiciones médicas) + recursos disponibles (vehículo, refugio alterno)**. |
| C-09 | **Auth con Clerk** (frontend) → al entrar el ciudadano cae en un lobby con el agente listo para conversar. |

### 2.2 Lo que sale (REMOVIDO del MVP)

| ID | Cambio |
|---|---|
| R-01 | Dashboards de gobierno, logística y salud (endpoints F-07, F-08, F-09). Quedan deprecated. |
| R-02 | Cálculo y exposición de **rutas alternativas (OSRM)** — F-04. Demasiado complejo para el nuevo enfoque y no aporta al ciudadano. |
| R-03 | Selector de actor en frontend. |
| R-04 | Mapeo de **datos de salud/epidemiología en el frontend**. Los datos se mantienen en DB (ver D-01) pero no se renderizan. |

### 2.3 Lo que se preserva con cambios (MODIFICADO)

| ID | Cambio |
|---|---|
| M-01 | Pipeline Open-Meteo se amplía: deja de muestrear solo en corredores y muestrea una **grilla nacional de Ecuador** para alimentar el heatmap de lluvia. Granularidad por definir (default propuesto: ~0.25°, ~150 puntos). |
| M-02 | NASA LHASA se sigue usando para riesgo predictivo de deslaves, pero también se expone una vista de **eventos near-real-time** (sin esperar a que el modelo de cascada los proyecte 24h). |
| M-03 | El modelo de cascada (F-05) deja de producir paquetes por actor y produce **risk_zones** + **risk_segments** que el agente y el frontend consumen directamente. |
| M-04 | Tablas y pipeline de salud permanecen en DB (intactos) pero marcados como **uso interno / contexto del bot**. No se eliminan. |

---

## 3. Decisiones tomadas

| # | Decisión | Justificación |
|---|---|---|
| D-01 | Datos de salud: **mantener en DB, ocultar en FE**. | El bot puede usarlos como contexto adicional (ej. "en tu zona, durante el Niño 2023, hubo brotes de X — incluye Y en tu kit"). Cero trabajo de migración. |
| D-02 | Inundaciones: **no usar API externa de inundaciones**. | No existe API que cubra Ecuador con buena resolución. Se infiere desde precipitación acumulada + susceptibilidad LHASA. |
| D-03 | Tiempo real de lluvia: **muestreo Open-Meteo "current"** sobre grilla nacional, refrescado al menos cada hora. | Open-Meteo expone `current_weather` y `precipitation` actual; es la fuente más viable para cubrir Ecuador completo sin costos. |
| D-04 | Plan del agente: **solo reactivo**. | Sin push notifications ni alertas proactivas en MVP. El ciudadano abre la app, conversa, recibe plan. |
| D-05 | Agente: **Claude Agent SDK con MCP in-process** (sin cambios respecto a lo ya decidido). | Coherente con decisión previa. |
| D-06 | Geometría de riesgo: **corredores + zonas administrativas (cantón/parroquia)**. | El ciudadano no siempre está sobre una carretera; necesita saber el riesgo del lugar donde vive. |
| D-07 | Fuente de POIs en mapa: por definir (ver §6 Open questions). |

---

## 4. Impacto por capa

### 4.1 PRD (`docs/PRD.md`)

Reescritura amplia:
- §1 Problema: pasar de "infraestructura crítica" a "riesgo catastrófico para ciudadanía".
- §2 Alcance: actores → usuario único ciudadano.
- §3 Modos: añadir **tiempo real** como tercer modo (junto a forecast y demo histórico).
- §4 Funcionalidades: reemplazar F-07/F-08/F-09 por endpoints centrados en el agente y en datos para el mapa ciudadano.
- §5 Post-MVP: mover P-01 (gobierno broadcast) y dashboards retirados; añadir notificaciones push del agente al usuario.
- §10 Out of scope: añadir "rutas alternativas", "dashboards por actor", "logística".

### 4.2 Backend (`app/`)

**Nuevos módulos / endpoints:**
- `app/agent/tools.py` → añadir tools del agente:
  - `get_my_risk(lat, lon)` — devuelve riesgo de la zona del usuario (deslaves, lluvia 24/48/72h, eventos en tiempo real).
  - `get_nearby_pois(lat, lon, types[])` — albergues, tiendas, ONGs, hospitales cercanos.
  - `get_realtime_rain(lat, lon, radius_km)` — lluvia actual en zona.
  - `web_search(query)` — tool wrapper sobre Tavily API (ayuda humanitaria, noticias locales).
  - `build_action_plan(profile, resources, location, risk_context)` — el LLM decide cómo combinar, pero esta tool puede estructurar el output final.
- `app/integrations/tavily.py` — cliente HTTP de Tavily Search API.
- `app/integrations/open_meteo.py` — extender para muestreo de grilla nacional + endpoint de tiempo real.
- `app/pipeline/realtime.py` — tarea de scheduler (cada 15-30 min) que refresca lluvia actual sobre la grilla nacional.
- `app/pipeline/zone_risk.py` — compute de riesgo por cantón/parroquia (cruzar LHASA + precipitación con polígonos administrativos).
- `app/api/v1/citizen.py` — nuevo router con endpoints públicos:
  - `GET /api/v1/realtime/rain?bbox=` — heatmap actual.
  - `GET /api/v1/realtime/landslides?bbox=` — eventos LHASA recientes.
  - `GET /api/v1/forecast/rain?bbox=&horizon=` — forecast por grilla.
  - `GET /api/v1/zones/risk?bbox=` — zonas administrativas con score.
  - `GET /api/v1/pois?bbox=&types=` — POIs útiles.
- `app/api/v1/agent.py` — extender endpoint `POST /api/v1/agent/chat` para aceptar `user_profile` y `user_location` en el contexto inicial de la sesión.

**Endpoints deprecated (marcar pero no eliminar todavía):**
- `GET /api/v1/dashboard/government`
- `GET /api/v1/dashboard/logistics[...]`
- `GET /api/v1/dashboard/health`

**Eliminaciones reales:**
- Cálculo OSRM de rutas alternativas (F-04). Borrar `app/pipeline/rerouting.py` (si existe), tabla `rerouting_plans` se mantiene por compatibilidad pero ya no se llena.

### 4.3 Modelo de datos

**Nuevas tablas:**
- `zones` — geometría de cantones/parroquias de Ecuador (seed desde INEC / OSM admin boundaries).
- `zone_risk_forecasts` — score de riesgo por zona × horizonte temporal.
- `realtime_rain_samples` — muestras de lluvia actual por punto de grilla × timestamp.
- `realtime_landslide_events` — eventos LHASA near-real-time.
- `pois` — albergues, tiendas, ONGs, hospitales (seed estático para demo).
- `agent_sessions` (opcional, solo si queremos historial cross-session; por ahora no — Claude Agent SDK maneja sesión con `resume`).

**Tablas preservadas tal cual (uso interno):**
- `municipalities` (incluye perfil epidemiológico) — fuente para que el bot enriquezca planes.
- `corridors`, `risk_forecasts`, `risk_segments` — siguen siendo válidos.
- `alerts` — se mantiene; el agente puede consultarlas.

**Tablas a deprecar (no borrar):**
- `rerouting_plans` — vacía a partir de este cambio.

### 4.4 Pipeline (APScheduler in-process)

| Job | Frecuencia | Acción |
|---|---|---|
| `ingest_open_meteo_forecast_grid` | 6h | Forecast 24/48/72h sobre grilla nacional. |
| `ingest_open_meteo_realtime_grid` | 30 min | Snapshot de lluvia actual sobre grilla nacional. |
| `ingest_lhasa_realtime` | 1h | Eventos LHASA del último período. |
| `ingest_lhasa_daily` | 24h | Susceptibilidad para forecast (igual que hoy). |
| `compute_zone_risk` | tras cada ingesta | Calcula score por zona administrativa. |
| `compute_cascade` | tras cada ingesta | Recalcula riesgo de corredores (ya existe). |

### 4.5 Frontend (referencia — fuera de este repo)

- Login Clerk → lobby con chat del agente abierto.
- Mapa interactivo con capas:
  - Heatmap de lluvia (tiempo real / forecast 24/48/72h toggleable).
  - Polígonos de zonas con score de riesgo.
  - Marcadores de eventos de deslave (forecast + tiempo real).
  - POIs filtrables.
- Sidebar con lista de corredores y zonas en riesgo.

---

## 5. Plan de acción (alto nivel — el plan ejecutable irá en otro doc)

1. **Actualizar PRD** con todos los cambios anteriores. Mantener historial dejando este MMD como referencia.
2. **Cliente Tavily** (`app/integrations/tavily.py`) + variable de entorno `TAVILY_API_KEY` + tool `web_search` en el agente.
3. **Extender pipeline de Open-Meteo** a grilla nacional (forecast + realtime).
4. **Ingesta LHASA near-real-time** (job 1h) y nueva tabla `realtime_landslide_events`.
5. **Seed de zonas administrativas** (cantones/parroquias de Ecuador) + job `compute_zone_risk`.
6. **Seed de POIs** (albergues SGR, hospitales MSP, ONGs principales). Definir formato CSV/GeoJSON para demo.
7. **Nuevo router `citizen.py`** con los endpoints listados en §4.2.
8. **Extender agente:** nuevas tools (`get_my_risk`, `get_nearby_pois`, `get_realtime_rain`, `web_search`, `build_action_plan`). Aceptar `user_profile` y `user_location` en `/agent/chat`.
9. **Marcar como deprecated** los endpoints de dashboards por actor (no eliminar; responder con header `Deprecation: true`).
10. **Eliminar pipeline OSRM** y limpiar referencias.
11. **Migración Alembic** consolidada con todos los cambios de schema.

---

## 6. Open questions

| # | Pregunta | Bloqueante para |
|---|---|---|
| Q-01 | ¿Fuente exacta de POIs por tipo? SGR Ecuador publica albergues; MSP publica establecimientos; ONGs requieren búsqueda manual o ReliefWeb. ¿Aceptamos seed manual para demo? | Paso 6 del plan |
| Q-02 | Granularidad final de la grilla nacional (~10km vs ~25km vs por cantón). | Paso 3 y 5 |
| Q-03 | ¿El perfil del ciudadano se persiste (Clerk metadata / tabla `users`) o vive solo en la sesión del agente? | Paso 8 |
| Q-04 | ¿Tavily se usa solo en demanda o también precalentamos resultados para los riesgos activos (cache)? | Paso 2 |
| Q-05 | ¿Mantenemos compatibilidad de los dashboards deprecated por cuánto tiempo? | Paso 9 |

---

## 7. Riesgos

- **Cuota de Open-Meteo:** muestrear cada 30 min sobre ~150 puntos = ~7,200 calls/día. Open-Meteo gratuito permite ~10k/día — viable pero ajustado. Mitigación: cachear y agrupar requests por bbox.
- **Costo Tavily:** API es de pago. Definir presupuesto y cuota por sesión del agente (ej. máx 3 búsquedas por turno).
- **LHASA near-real-time:** el producto "daily" no es realmente en tiempo real (latencia ~24h). Validar si NASA expone un feed más fresco o si tenemos que ajustar la promesa del "tiempo real" a "últimos eventos confirmados".
- **Seed manual de POIs:** trabajo no-código que el equipo necesita asignar.
- **Deuda con código eliminado:** rerouting/OSRM tiene tests y tablas; al deprecar puede dejar referencias rotas si no se limpia.

---

## 8. Referencia rápida de mapeo (antes → después)

| Antes | Después |
|---|---|
| Multi-actor (gobierno / logística / salud) | Solo ciudadano |
| Dashboards REST por actor | Endpoints públicos + agente conversacional |
| Rutas alternativas OSRM | Eliminado |
| Salud en frontend | Salud solo como contexto interno del bot |
| Mapa centrado en corredores | Mapa nacional con heatmap + zonas + corredores + POIs |
| Solo predictivo | Predictivo + tiempo real |
| Sin web search | Tavily como tool del agente |
| Sin perfil de usuario | Ciudadano aporta ubicación + perfil + recursos |
