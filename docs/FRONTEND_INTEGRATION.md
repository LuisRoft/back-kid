# Guía de integración Frontend — back-kid

> **Audiencia:** equipo del frontend
> **Backend host (local):** `http://127.0.0.1:8000`
> **Prefijo API:** `/api/v1`
> **Estado del MVP:** ciudadano-céntrico, agente conversacional reactivo (Clerk-protegido), mapa con datos reales de Ecuador.

---

## 1. Modos de operación del backend

El backend opera **tres modos en paralelo** y los expone como **endpoints distintos**. El FE elige cuáles renderizar:

| Modo | Qué responde | Fuente |
|---|---|---|
| **Predictivo** | "¿Qué riesgo va a haber en las próximas 24 / 48 / 72 horas?" | Open-Meteo (forecast) × NASA LHASA (susceptibilidad) |
| **Tiempo real** | "¿Qué está pasando ahora mismo?" | Open-Meteo (current weather) + sintetizador de eventos NRT |
| **Demo histórico (opcional)** | Datos del Fenómeno El Niño 2023 en Ecuador | Seed estático pre-cargado |

### Sobre el modo Demo histórico
- Se activa con `DEMO_MODE=true` en el backend.
- **Actualmente está `false`** → estás viendo data en vivo.
- Cuando se activa, **NO reemplaza** la data en vivo — la suma. El FE puede seleccionar `?is_demo=true` o `?is_demo=false` en los endpoints que lo soporten para distinguir.
- Incluye corredores, forecasts y alertas del Niño 2023 con probabilidades históricas reales. No solo deslaves: también risk_segments y alerts.
- **Útil para demo cuando no hay actividad en vivo significativa.**

---

## 2. Estado actual de los datos (snapshot)

Cuántas filas tiene cada tabla **ahora mismo en Supabase**:

| Capa | Endpoint | Filas en DB | Datos visibles esperados |
|---|---|---|---|
| Corredores | `/api/v1/map/corridors` | 26 | ✅ líneas grises de carreteras |
| Tramos en riesgo | `/api/v1/map/risk-segments` | 1,704 | ✅ tramos amarillo→rojo |
| Cantones | `/api/v1/map/zones?horizon=24` | 223 | ✅ polígonos |
| **Riesgo por cantón** | `/api/v1/map/zones?horizon=24` | **660 forecasts activos** (220 zonas × 3 horizontes) | ✅ polígonos **coloreados por riesgo** |
| POIs | `/api/v1/map/pois` | 9,680 | ✅ hospitales, clínicas, farmacias, supermercados |
| Lluvia ahora | `/api/v1/map/rain/realtime` | 725 (algunas viejas) | ⚠️ vacío si filtro `within_minutes=90` y muestras stale |
| Deslaves ahora | `/api/v1/map/landslides/realtime` | 0 | ⚠️ esperado — no llueve fuerte en susceptibilidad alta |
| Alertas oficiales | `/api/v1/alerts` | 56 | ✅ |

---

## 3. Endpoints para el mapa (todos públicos, sin auth)

Base: `GET http://127.0.0.1:8000/api/v1/map/`

### 3.1 Capas PREDICTIVAS

| Capa visual | Endpoint | Params |
|---|---|---|
| Corredores monitoreados | `/map/corridors` | `is_demo=true\|false` (default false) |
| Tramos de carretera en riesgo | `/map/risk-segments` | `horizon=24\|48\|72`, `min_probability=0.0..1.0` (default 0.65), `is_demo` |
| Polígonos cantón con score | `/map/zones` | `bbox=west,south,east,north`, `horizon=24\|48\|72`, `level=canton` (default) |
| Heatmap forecast de lluvia | `/map/rain/forecast` | `bbox`, `horizon=24\|48\|72` (es alias de `/map/zones`) |
| Predicción de deslaves | `/map/landslides/forecast` | `min_probability`, `is_demo` (alias de `/map/risk-segments`) |

### 3.2 Capas en TIEMPO REAL

| Capa visual | Endpoint | Params |
|---|---|---|
| Lluvia ahora (heatmap) | `/map/rain/realtime` | `bbox`, `within_minutes=10..360` (default 90) |
| Deslaves reportados últimas N horas | `/map/landslides/realtime` | `bbox`, `hours=1..168` (default 24) |

### 3.3 POIs (estáticos, refrescan cada 7 días)

| Endpoint | Params |
|---|---|
| `/map/pois` | `bbox`, `types=hospital,clinic,pharmacy,supermarket` (cualquier subconjunto), `limit=1..5000` |

### 3.4 Alertas oficiales (separadas del prefijo `/map`)

| Endpoint |
|---|
| `/api/v1/alerts` — lista todas las activas |
| `/api/v1/alerts/corridor/{corridor_id}` — filtra por corredor |

---

## 4. Formato de respuesta — GeoJSON FeatureCollection

Todos los endpoints de `/map/*` devuelven el mismo formato estándar consumible directo por Mapbox GL / MapLibre / Leaflet:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "properties": {
        "id": "...",
        "name": "Quito",
        "probability": 0.95,
        "horizon_hours": 24,
        "risk_level": "critical",
        "risk_color": "#7f1d1d"
      }
    }
  ]
}
```

### Properties extra en `/map/zones` — "¿Por qué esa zona tiene riesgo?"

Cada feature de `/map/zones` ahora trae el **desglose** que explica el score:

```json
{
  "type": "Feature",
  "geometry": { "type": "MultiPolygon", "coordinates": [...] },
  "properties": {
    "id": "uuid",
    "code": "ECU.19.6_1",
    "name": "Quito",
    "level": "canton",
    "horizon_hours": 24,
    "probability": 0.95,
    "risk_level": "critical",
    "risk_color": "#7f1d1d",
    "expected_rainfall_mm": 78.3,        // ← NUEVO: lluvia acumulada esperada en esa ventana
    "peak_susceptibility_class": 4,      // ← NUEVO: peor susceptibilidad LHASA (0-5)
    "computed_at": "2026-05-17T19:43:26+00:00"
  }
}
```

**Cómo interpretar:**
- `expected_rainfall_mm` — milímetros de precipitación pronosticada en la ventana del horizonte (24h, 48h ó 72h). Es el peak entre los puntos muestreados dentro del polígono del cantón.
- `peak_susceptibility_class` — escala 0-5 de NASA LHASA:
  - `0` agua / sin dato
  - `1-2` baja susceptibilidad
  - `3` moderada
  - `4-5` alta / muy alta
- `computed_at` — cuándo se calculó (ISO 8601 UTC). Útil para mostrar "actualizado hace X min".

**Para el tooltip o popup del cantón** (ejemplo de copy):
> **Quito** — riesgo CRÍTICO a 24h (95%)
> Lluvia esperada: **78.3 mm en 24h**
> Susceptibilidad del terreno: **alta (clase 4)**
> Actualizado hace 12 min

**Importante:** los campos `expected_rainfall_mm` y `peak_susceptibility_class` pueden venir `null` durante una breve ventana después de la migración hasta que el job `zone_risk` se ejecute (cada 6h). Mientras tanto el FE debe manejar `null` mostrando "—" o "no disponible".

### Niveles de riesgo y colores (los devuelve el backend ya resueltos)

| Probabilidad | `risk_level` | `risk_color` |
|---|---|---|
| ≥ 0.85 | `critical` | `#7f1d1d` (rojo oscuro) |
| ≥ 0.65 | `high` | `#ef4444` (rojo) |
| ≥ 0.45 | `moderate` | `#f97316` (naranja) |
| ≥ 0.20 | `low` | `#eab308` (amarillo) |
| < 0.20 | `none` | `#22c55e` (verde) |

**Recomendación al FE:** usar directamente `risk_color` de las properties en lugar de recalcular — garantiza consistencia entre mapa, sidebar y chat del agente.

---

## 5. Por qué pueden estar vacías algunas capas (debug rápido)

### `/map/landslides/realtime` devuelve 0 features
- **No es bug.** La capa sintetiza eventos con la regla: `precipitación >= 5 mm/h` **Y** `susceptibilidad LHASA >= 4`.
- Si no llueve fuerte en zonas susceptibles ahora, **no hay eventos**, así de simple.
- **UX recomendada:** mostrar "Sin deslaves reportados en últimas 24h" en el toggle de la capa, para no parecer roto.

### `/map/rain/realtime` devuelve 0 features
- Filtro por defecto: muestras de últimos `within_minutes=90`.
- Si las muestras son más viejas, no aparecen.
- **Probar con `?within_minutes=400`** para ver las que sí están en DB.
- **Causa raíz**: backend hit rate limit de Open-Meteo (10k calls/día por IP). Se resetea a medianoche UTC.

### `/map/zones?horizon=24` muestra polígonos pero `probability=null` en muchos
- Algunos cantones (Galápagos, 2-3 más) no tienen forecast porque sus coords caen fuera del raster LHASA o porque la API de clima falló transitoriamente.
- **UX recomendada:** polígonos con `probability=null` se pintan gris claro (`#9ca3af`) o sin opacidad.

### El FE ve 0 features pero el endpoint en curl devuelve muchas
- Revisar CORS — backend permite `*` por defecto, pero si hay proxy intermedio puede romper.
- Revisar que el FE no esté hardcoded a `is_demo=true`, que filtraría solo data demo (que está vacía si `DEMO_MODE=false`).

---

## 6. Endpoint del agente conversacional (privado, requiere Clerk)

```
POST http://127.0.0.1:8000/api/v1/agent/chat
Headers:
  Authorization: Bearer <clerk_jwt>
  Content-Type: application/json

Body:
{
  "message": "qué riesgo tengo en mi zona y qué hago?",
  "session_id": "opcional para continuar conversación"
}
```

**Respuesta**: Server-Sent Events (SSE) streaming.

Cada chunk es uno de estos:

```
data: {"type": "text", "text": "..."}
data: {"type": "done", "session_id": "abc-123", "is_error": false}
data: [DONE]
```

### Cómo configurar el JWT en Clerk
- Dashboard de Clerk → **JWT Templates** → tu template (o `default`) → añadir claim:
  ```json
  { "profile": "{{user.unsafe_metadata}}" }
  ```
- El backend extrae automáticamente del JWT: `clerk_user_id` (sub), `email`, y el `profile` del ciudadano (ubicación, familia, recursos, condiciones médicas).
- **No mandes el perfil en el body.** Viaja en el JWT.

### Perfil del ciudadano — shape esperado en `unsafeMetadata`

```ts
type CitizenProfile = {
  onboardingComplete: boolean
  location: { lat: number, lon: number, label?: string }
  family_size: number
  has_kids: boolean
  has_elderly: boolean
  medical_conditions: string[]   // ej. ["diabetes"]
  has_vehicle: boolean
  alternate_shelter?: { lat: number, lon: number, label?: string }
  locale?: 'es-EC' | 'en-US'
}
```

El FE escribe esto con `user.update({ unsafeMetadata: { ...profile } })` desde la página de onboarding o desde una custom page del `<UserProfile>` de Clerk.

---

## 7. Flujo recomendado para el FE

```
1. Usuario abre la app
        ↓
2. Clerk → SignIn / SignUp
        ↓
3. middleware revisa user.unsafeMetadata.onboardingComplete
   - false → redirect a /onboarding (form propio: ubicación + perfil)
   - true  → /lobby
        ↓
4. /lobby:
   a) MAPA con capas (ver §3):
      - GET /map/corridors          → líneas gris
      - GET /map/risk-segments      → líneas color (alerts viales)
      - GET /map/zones?horizon=24   → coropleto cantones
      - GET /map/rain/realtime      → heatmap azul-violeta
      - GET /map/landslides/realtime → markers pulsantes
      - GET /map/pois?types=...     → markers por tipo
   b) Toggle Predicción <-> Tiempo real
   c) Selector 24h / 48h / 72h para predicción
   d) SIDEBAR:
      - "Tu zona"     → filtra zones por bbox de profile.location
      - "Alertas"     → GET /alerts
   e) CHAT del agente:
      - POST /agent/chat con Authorization: Bearer <jwt>
      - Stream SSE
        ↓
5. Edición del perfil:
   <UserButton> → custom page "Mi perfil de riesgo"
   → reusa el componente de onboarding
   → user.update({ unsafeMetadata })
```

---

## 8. Ejemplos de curl listos para copiar

```bash
BASE=http://127.0.0.1:8000

# Lo básico siempre disponible
curl "$BASE/health"
curl "$BASE/api/v1/map/corridors"
curl "$BASE/api/v1/map/risk-segments?horizon=24"

# Predictivo por cantón
curl "$BASE/api/v1/map/zones?horizon=24"
curl "$BASE/api/v1/map/zones?bbox=-79.0,-1.0,-78.0,0.0&horizon=24"  # filtrado por bbox

# Tiempo real (puede estar vacío hoy)
curl "$BASE/api/v1/map/rain/realtime"
curl "$BASE/api/v1/map/rain/realtime?within_minutes=400"  # buscar samples viejas
curl "$BASE/api/v1/map/landslides/realtime?hours=24"

# POIs
curl "$BASE/api/v1/map/pois?types=hospital,pharmacy&limit=50"

# Alertas oficiales
curl "$BASE/api/v1/alerts"

# Agente (necesita JWT real de Clerk)
curl -N \
  -H "Authorization: Bearer $CLERK_JWT" \
  -H "Content-Type: application/json" \
  -d '{"message":"qué riesgo tengo y qué hago"}' \
  "$BASE/api/v1/agent/chat"
```

---

## 9. Frecuencia de actualización de los datos

| Job | Cuándo corre | Qué actualiza |
|---|---|---|
| `risk_pipeline` | cada 30 min | corredores + risk_segments + alerts |
| `realtime_rain` | cada 30 min | snapshot de lluvia actual (grilla nacional) |
| `lhasa_realtime` | cada 60 min | eventos NRT sintetizados desde lluvia + susceptibilidad |
| `zone_risk` | **cada 6 h** | score por cantón × horizonte |
| `pois_refresh` | cada 7 días | POIs desde OSM Overpass |

**Implicación para el FE:**
- Datos del mapa son "casi tiempo real" pero no instantáneos. Refrescar cada 5 min en el FE es razonable.
- `zone_risk` (coropleto cantonal) cambia cada 6h. Refrescar más seguido en el FE es desperdicio de bandwidth.
- POIs son prácticamente estáticos. Cachear agresivamente en el FE.

---

## 10. Checklist de QA para el equipo FE

Antes de decir "no veo data":

- [ ] Backend levantado y `curl http://127.0.0.1:8000/health` devuelve 200.
- [ ] Endpoint puro de mapa con `curl` devuelve `features=N>0`.
- [ ] CORS no está siendo bloqueado (revisar DevTools network tab).
- [ ] El FE NO está pasando `is_demo=true` si `DEMO_MODE=false` en backend (devolvería vacío).
- [ ] El `bbox` que pasa el FE es válido (`west<east`, `south<north`) y cubre Ecuador (lng ~-81 a -75, lat ~-5 a 2).
- [ ] Para `/agent/chat`: header `Authorization: Bearer <token>` está presente y el token no expiró.
- [ ] El JWT template en Clerk incluye el claim `profile`.

---

## 11. Contacto y issues

- Backend host (deploy futuro): Railway
- DB: Supabase (PostgreSQL + PostGIS)
- Issues técnicos del backend → equipo backend
- Issues del agente / perfil → revisar primero JWT y `unsafeMetadata`, después backend

> Última actualización: 2026-05-17 (pivote ciudadano completado, mapa con data real en DB).
