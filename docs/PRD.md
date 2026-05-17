# PRD — back-kid (Backend)

**Proyecto:** Sistema de alerta temprana para protección de infraestructura crítica  
**Track:** DEF/ACC — Hackathon Latam  
**Scope del backend:** API + pipeline de datos satelitales  
**Arquitectura técnica:** Ver [architecture.md](./architecture.md)

---

## 1. Problema

El Fenómeno del Niño genera cascadas de fallas en infraestructura crítica que hoy nadie modela de forma anticipada. Los pronósticos climáticos existen (NOAA, Open-Meteo), pero no hay sistema que conecte esos pronósticos con el impacto concreto en carreteras, logística y salud. Todo es reactivo.

El backend de este sistema es el motor que convierte señales climáticas en inteligencia accionable con 24-72 horas de anticipación.

---

## 2. Alcance MVP

**País:** Ecuador  
**Corredores:** Detectados automáticamente por el pipeline (OSM + NASA LHASA)  
**Cascadas modeladas:** Logística/alimentos · Sistema de salud  
**Actores:** Gobierno · Logística · Salud (sin roles de auth — selector en frontend)  
**Auth:** Clerk (manejado en frontend; backend valida JWT si se requiere en el futuro)

---

## 3. Modos de operación

El sistema opera en dos modos simultáneos:

| Modo | Descripción |
|---|---|
| **Tiempo real** | Pipeline activo conectado a Open-Meteo + NASA LHASA. Forecasts actualizados cada 6h. |
| **Demo histórico** | Datos del Niño 2023 en Ecuador pre-cargados. Cierres reales documentados disponibles para demostración cuando no hay actividad significativa en tiempo real. |

El frontend puede indicar qué modo mostrar. El backend sirve ambos datasets desde la misma estructura de DB.

---

## 4. Funcionalidades del backend — MVP

### 4.1 Pipeline de ingesta

**F-01 — Ingesta meteorológica (cada 6h)**
- Consume Open-Meteo API para Ecuador (bbox: lat -5°/2°, lon -81°/-75°)
- Extrae: precipitación acumulada 24/48/72h, probabilidad de lluvia extrema
- Guarda en DB como serie temporal por punto de grilla

**F-02 — Ingesta LHASA (cada 24h)**
- Descarga el NetCDF diario de NASA LHASA (landslide hazard nowcast)
- Recorta al bbox de Ecuador con rasterio
- Convierte celdas de alta susceptibilidad (> umbral) a geometrías vectoriales
- Intersecta con red vial OSM para identificar segmentos en riesgo
- Guarda segmentos de carretera con su probabilidad de cierre en DB

**F-03 — Red vial OSM (startup + semanal)**
- Descarga red vial de Ecuador con osmnx
- Carga en PostGIS como geometrías de segmento
- Calcula para cada segmento: population impact (CEPAL), municipios dependientes

**F-04 — Rutas alternativas (tras F-03)**
- Para cada corredor crítico detectado, consulta OSRM para obtener rutas alternativas
- Pre-computa y guarda en DB con: distancia adicional, tiempo estimado, geometría

### 4.2 Modelo de cascada

**F-05 — Cascade compute (tras cada ingesta)**
- Cruza probabilidad de lluvia extrema (F-01) con susceptibilidad de deslave (F-02)
- Genera `risk_forecast` por corredor × horizonte temporal (24h / 48h / 72h)
- Si `probability > RISK_THRESHOLD`: genera `alert` y activa paquete de inteligencia para cada actor

**F-06 — Perfil epidemiológico**
- Datos históricos PAHO/SIVIGILA pre-cargados por municipio
- Para municipios con riesgo de aislamiento vial: adjunta perfil de enfermedades durante El Niño anteriores y recomendación de insumos a pre-posicionar

### 4.3 API REST

Base path: `/api/v1`

**F-07 — Dashboard Gobierno**
```
GET /api/v1/dashboard/government
```
Retorna lista priorizada de corredores en riesgo, ordenados por impacto poblacional. Incluye forecasts 24/48/72h por corredor y municipios que quedarían aislados.

**F-08 — Dashboard Logística**
```
GET /api/v1/dashboard/logistics
GET /api/v1/dashboard/logistics/{corridor_id}
```
Retorna plan de rerouting por corredor: ruta alternativa con geometría, distancia adicional, tiempo estimado, y forecast de cierre.

**F-09 — Dashboard Salud**
```
GET /api/v1/dashboard/health
```
Retorna mapa de municipios en riesgo de aislamiento con perfil epidemiológico histórico y recomendación de insumos a pre-posicionar por corredor disponible.

**F-10 — Alertas activas**
```
GET /api/v1/alerts
GET /api/v1/alerts/{alert_id}
```
Lista de alertas generadas actualmente. Cada alerta incluye: corredor afectado, probabilidad, horizonte, y paquetes de inteligencia por actor.

**F-11 — Estado del pipeline**
```
GET /api/v1/pipeline/status
```
Último run exitoso de cada tarea, próximo run programado. Útil para debugging y transparencia.

---

## 5. Funcionalidades pendientes (post-MVP)

**P-01 — Government action broadcast**  
El gobierno puede publicar acciones tomadas (pre-posicionamiento de equipos, cierre de rutas, envío de insumos). Visible para todos los actores como feed en tiempo real. Requiere: `POST /api/v1/actions`, `GET /api/v1/actions/feed`.

**P-02 — Seguimiento post-evento**  
El sistema registra si el cierre predicho efectivamente ocurrió. Compara predicción vs realidad para validar y mejorar el modelo. Requiere: campo `actual_outcome` en `alerts`, job de validación post-evento.

**P-03 — Notificaciones push/webhook**  
Cuando se genera una alerta nueva, notificar a los actores relevantes por webhook o email.

**P-04 — Expansión de país**  
Agregar Colombia. Requiere parametrizar el pipeline por bbox de país y agregar fuentes epidemiológicas de SIVIGILA Colombia.

**P-05 — AI Agent (chatbot conversacional)**  
Agente conversacional embebido en la aplicación que permite consultar el estado del sistema en lenguaje natural.

*Stack:*
- **Claude Agent SDK** (`claude-agent-sdk` Python package) — manejo de sesión, tool-calling y loop del agente automático
- No se usa LangChain ni LangGraph
- Endpoint: `POST /api/v1/agent/chat` — recibe `{ message, session_id? }`, responde en streaming

*Cómo funciona:*
- Las tools se definen con `@tool` + `create_sdk_mcp_server` — corren **in-process** dentro de FastAPI, no como subprocess separado
- Los handlers son funciones async Python que llaman directamente al service/repo layer
- Sesión manejada con `resume=session_id` built-in del SDK — sin implementar historial manualmente
- Built-in tools del SDK (Read, Write, Bash) deshabilitados con `tools=[]`

*Definición acordada:*
- **Memoria:** por sesión via `resume=session_id`. Al cerrar el chat, se descarta. Sin persistencia cross-session.
- **Acciones:** read-only — el agente solo consulta datos, no modifica estado.
- **Contexto de actor:** ninguno — agnóstico a quién pregunta, responde con todos los datos disponibles.
- **Comportamiento:** reactivo — solo responde cuando el usuario pregunta.

*Tools del agente (in-process, llaman directamente al repo layer):*
- `get_corridor_risks(horizon_hours)` — corredores en riesgo con forecasts 24/48/72h
- `get_rerouting_plan(corridor_id)` — rutas alternativas para un corredor específico
- `get_health_risk(min_probability)` — municipios en riesgo de aislamiento con perfil epidemiológico
- `get_active_alerts()` — alertas activas en este momento

*Ubicación en el proyecto:* `app/agent/` — tool definitions + chat handler (endpoint)

---

## 6. Modelo de datos (resumen)

| Tabla | Contenido |
|---|---|
| `corridors` | Segmentos de carretera de Ecuador con geometría PostGIS e impacto poblacional |
| `risk_forecasts` | Probabilidad de cierre por corredor × horizonte (24/48/72h) × timestamp |
| `risk_segments` | Tramos específicos de un corredor con riesgo por horizonte y geometría propia |
| `municipalities` | Geometría + perfil epidemiológico histórico PAHO |
| `alerts` | Alertas generadas cuando probability > threshold |
| `rerouting_plans` | Rutas alternativas pre-computadas por corredor |
| `pipeline_runs` | Log de ejecución de cada tarea del pipeline |

---

## 7. Fuentes de datos

| Dataset | Fuente | Frecuencia de actualización |
|---|---|---|
| Precipitación forecast | Open-Meteo API | Cada 6h |
| Landslide hazard | NASA LHASA (NetCDF) | Diaria |
| Red vial | OpenStreetMap via osmnx | Startup + semanal |
| Rutas alternativas | OSRM public API | Pre-computado |
| Perfil epidemiológico | PAHO / SIVIGILA (CSV) | Pre-cargado (histórico) |
| Población por zona | CEPAL / INEC Ecuador | Pre-cargado |
| Demo histórico | El Niño 2023 Ecuador | Seed estático |

Todas las fuentes son **públicas y gratuitas**. Sin API keys para el MVP.

---

## 8. Requisitos no funcionales

- Latencia API: < 200ms por endpoint (datos pre-computados, no cálculo on-demand)
- Pipeline: tolerante a fallos — si un run falla, el siguiente ciclo reintenta
- CPU-bound steps del pipeline: `run_in_executor` para no bloquear el event loop de FastAPI
- Configuración: todas las variables de entorno tipadas en `app/config.py` via pydantic-settings
- Sin secrets en código — todas las credenciales por variables de entorno

---

## 9. Deployment

| Servicio | Plataforma |
|---|---|
| Backend (FastAPI + pipeline) | Railway |
| Base de datos | Supabase (PostgreSQL + PostGIS) |
| Frontend | Vercel |

---

## 10. Out of scope (MVP)

- Roles de usuario y control de acceso por actor
- Autenticación en el backend (Clerk se gestiona en el frontend)
- Notificaciones push o email
- Cobertura fuera de Ecuador
- Interfaz de administración
