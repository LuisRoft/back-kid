from __future__ import annotations

import logging
from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool
from geoalchemy2.functions import ST_Contains, ST_MakePoint, ST_SetSRID
from sqlalchemy import select

from app.agent import quota
from app.config import settings
from app.db.repositories.alert_repo import AlertRepo
from app.db.repositories.corridor_repo import CorridorRepo
from app.db.repositories.poi_repo import PoiRepo
from app.db.repositories.realtime_landslide_repo import RealtimeLandslideRepo
from app.db.repositories.realtime_rain_repo import RealtimeRainRepo
from app.db.repositories.zone_repo import ZoneRepo
from app.db.repositories.zone_risk_repo import ZoneRiskRepo
from app.db.session import AsyncSessionLocal
from app.integrations.tavily import TavilyError, search as tavily_search
from app.models.municipality import Municipality

log = logging.getLogger(__name__)

VALID_POI_TYPES = {"hospital", "clinic", "pharmacy", "supermarket"}


def _severity(probability: float) -> str:
    if probability >= 0.85:
        return "HIGH"
    if probability >= 0.70:
        return "MEDIUM"
    return "LOW"


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


# ----------------------------------------------------------- get_active_alerts


@tool(
    "get_active_alerts",
    "Devuelve todas las alertas oficiales activas generadas por el sistema (corredores con "
    "probabilidad de cierre ≥ 65%). Útil cuando el ciudadano pregunta '¿qué está pasando ahora?' "
    "o '¿hay alguna alerta?'.",
    {},
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def get_active_alerts(args: dict[str, Any]) -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as session:
            alerts = await AlertRepo(session).list_active(is_demo=False)
            if not alerts:
                return _ok("No hay alertas oficiales activas en este momento.")
            corridors = await CorridorRepo(session).list_all(is_demo=False)
            corridor_map = {c.id: c.name for c in corridors}

        lines = [f"**Alertas activas ({len(alerts)}):**"]
        for a in sorted(alerts, key=lambda x: x.probability, reverse=True):
            name = corridor_map.get(a.corridor_id, str(a.corridor_id))
            lines.append(
                f"- [{_severity(a.probability)}] **{name}** — {int(a.probability * 100)}% "
                f"(horizonte {a.horizon_hours}h, emitida {a.generated_at.strftime('%Y-%m-%d %H:%M UTC')})"
            )
        return _ok("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        log.exception("get_active_alerts failed")
        return _err(f"Error consultando alertas: {exc}")


# ---------------------------------------------------------------- get_my_risk


@tool(
    "get_my_risk",
    "Devuelve el riesgo en la zona del ciudadano: pronóstico de lluvia/deslave 24/48/72h, "
    "zona administrativa que lo contiene, y eventos en tiempo real recientes en su área. "
    "Llama esto PRIMERO cuando el ciudadano pregunte por su situación personal.",
    {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitud del ciudadano."},
            "lon": {"type": "number", "description": "Longitud del ciudadano."},
        },
        "required": ["lat", "lon"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def get_my_risk(args: dict[str, Any]) -> dict[str, Any]:
    lat = float(args["lat"])
    lon = float(args["lon"])

    try:
        async with AsyncSessionLocal() as session:
            zone = await ZoneRepo(session).find_containing_point(lat, lon, level="canton")
            zone_forecasts = (
                await ZoneRiskRepo(session).list_by_zone(zone.id, only_active=True)
                if zone
                else []
            )
            recent_landslides = await RealtimeLandslideRepo(session).recent_near(
                lat, lon, radius_km=50.0, hours=24, limit=5
            )
            recent_rain = await RealtimeRainRepo(session).latest_near(
                lat, lon, radius_km=10.0, within_minutes=90, limit=3
            )

        lines = [f"**Riesgo en tu zona (lat={lat:.4f}, lon={lon:.4f})**"]
        if zone:
            lines.append(f"- Cantón: **{zone.name}** ({zone.code})")
        else:
            lines.append("- No se encontró cantón administrativo para esta ubicación (¿fuera de Ecuador?).")

        if zone_forecasts:
            lines.append("- Pronóstico de riesgo por horizonte:")
            for f in zone_forecasts:
                lines.append(
                    f"  - {f.horizon_hours}h → {int(f.probability * 100)}% [{_severity(f.probability)}]"
                )
        else:
            lines.append("- Pronóstico por zona: sin datos para esta zona aún.")

        if recent_rain:
            avg_mm = sum(r.precipitation_mm_h for r in recent_rain) / len(recent_rain)
            latest = max(r.observed_at for r in recent_rain)
            lines.append(
                f"- Lluvia reciente (radio 10 km): promedio {avg_mm:.1f} mm/h, "
                f"última medición {latest.strftime('%H:%M UTC')}"
            )
        else:
            lines.append("- Lluvia reciente (radio 10 km): sin muestras recientes.")

        if recent_landslides:
            lines.append("- Eventos de deslave reportados en últimas 24h (radio 50 km):")
            for e in recent_landslides:
                lines.append(
                    f"  - [{e.severity.upper()}] {e.lat:.4f}, {e.lon:.4f} — "
                    f"{e.reported_at.strftime('%Y-%m-%d %H:%M UTC')}"
                )
        else:
            lines.append("- Sin eventos de deslave reportados en últimas 24h.")

        return _ok("\n".join(lines))

    except Exception as exc:  # noqa: BLE001
        log.exception("get_my_risk failed")
        return _err(f"Error consultando riesgo personal: {exc}")


# ----------------------------------------------------------- get_realtime_rain


@tool(
    "get_realtime_rain",
    "Muestras de precipitación actual en un radio (km) alrededor de un punto. Útil cuando el "
    "ciudadano pregunta '¿está lloviendo donde estoy?' o '¿qué tan fuerte llueve ahora?'.",
    {
        "type": "object",
        "properties": {
            "lat": {"type": "number"},
            "lon": {"type": "number"},
            "radius_km": {"type": "number", "description": "Default 10 km."},
        },
        "required": ["lat", "lon"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def get_realtime_rain(args: dict[str, Any]) -> dict[str, Any]:
    lat = float(args["lat"])
    lon = float(args["lon"])
    radius_km = float(args.get("radius_km", 10.0))

    try:
        async with AsyncSessionLocal() as session:
            samples = await RealtimeRainRepo(session).latest_near(
                lat, lon, radius_km=radius_km, within_minutes=90, limit=20
            )
        if not samples:
            return _ok(
                f"Sin muestras de lluvia recientes (≤90 min) en radio de {radius_km:.0f} km."
            )

        avg = sum(s.precipitation_mm_h for s in samples) / len(samples)
        peak = max(s.precipitation_mm_h for s in samples)
        latest = max(s.observed_at for s in samples)
        intensity = (
            "extrema" if peak >= 12
            else "fuerte" if peak >= 5
            else "moderada" if peak >= 1
            else "ligera"
        )
        return _ok(
            f"**Lluvia actual** (radio {radius_km:.0f} km, {len(samples)} muestras):\n"
            f"- Promedio: {avg:.2f} mm/h\n"
            f"- Pico: {peak:.2f} mm/h ({intensity})\n"
            f"- Última muestra: {latest.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("get_realtime_rain failed")
        return _err(f"Error consultando lluvia en tiempo real: {exc}")


# ------------------------------------------------------------ get_nearby_pois


@tool(
    "get_nearby_pois",
    "POIs útiles cercanos al ciudadano: hospital, clinic, pharmacy, supermarket. Devuelve "
    "los k más cercanos. Usa esta tool para sugerir lugares concretos en el plan de acción.",
    {
        "type": "object",
        "properties": {
            "lat": {"type": "number"},
            "lon": {"type": "number"},
            "types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Subconjunto de: hospital, clinic, pharmacy, supermarket. Si se omite, todos.",
            },
            "k": {"type": "integer", "description": "Cantidad (default 5)."},
        },
        "required": ["lat", "lon"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def get_nearby_pois(args: dict[str, Any]) -> dict[str, Any]:
    lat = float(args["lat"])
    lon = float(args["lon"])
    k = int(args.get("k", 5))
    raw_types = args.get("types") or []

    types: list[str] | None
    if raw_types:
        types = [t for t in raw_types if t in VALID_POI_TYPES]
        invalid = [t for t in raw_types if t not in VALID_POI_TYPES]
        if invalid:
            return _err(
                f"Tipos inválidos: {invalid}. Permitidos: {sorted(VALID_POI_TYPES)}."
            )
    else:
        types = None

    try:
        async with AsyncSessionLocal() as session:
            pois = await PoiRepo(session).nearest(
                lat, lon, types=types, k=k, radius_km=25.0
            )

        if not pois:
            scope = ", ".join(types) if types else "cualquier tipo"
            return _ok(
                f"Sin POIs de tipo [{scope}] en 25 km. Sugiere `web_search` si el ciudadano "
                f"necesita ayuda externa (albergues, ONGs)."
            )

        lines = [f"**POIs cercanos a ({lat:.4f}, {lon:.4f})**:"]
        for p in pois:
            name = p.name or "(sin nombre)"
            addr = f" — {p.address}" if p.address else ""
            lines.append(f"- [{p.type}] **{name}**{addr}")
        return _ok("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        log.exception("get_nearby_pois failed")
        return _err(f"Error consultando POIs: {exc}")


# ----------------------------------------------------------------- web_search


@tool(
    "web_search",
    "Busca en internet información en vivo (albergues activos, ayuda humanitaria, noticias "
    "locales, alertas oficiales recientes). Úsala SOLO cuando la base de datos no tiene la "
    "información (típicamente albergues y ONGs). Tienes un máximo de 3 búsquedas por turno.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Consulta natural; incluye ubicación (ej. cantón) y fechas si es relevante.",
            }
        },
        "required": ["query"],
    },
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
)
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return _err("La consulta `query` no puede estar vacía.")

    allowed, remaining = quota.check_and_increment(
        max_calls=settings.AGENT_WEB_SEARCH_MAX_PER_TURN
    )
    if not allowed:
        return _err(
            f"Cuota de búsqueda web agotada para esta sesión "
            f"(máx {settings.AGENT_WEB_SEARCH_MAX_PER_TURN}). "
            f"Responde con la información que ya tienes."
        )

    try:
        result = await tavily_search(query, max_results=5)
    except TavilyError as exc:
        return _err(f"Búsqueda web no disponible: {exc}")

    answer = result.get("answer") or ""
    items = result.get("results") or []
    lines = [f"**Búsqueda web** (`{query}`)"]
    if answer:
        lines.append(f"\n_Resumen:_ {answer}")
    if items:
        lines.append("\n_Resultados:_")
        for r in items[:5]:
            title = r.get("title") or "(sin título)"
            url = r.get("url") or ""
            content = (r.get("content") or "")[:300]
            lines.append(f"- **{title}** — {url}\n  {content}")
    lines.append(f"\n_(Quedan {remaining} búsquedas en este turno.)_")
    return _ok("\n".join(lines))


# --------------------------------------------------- get_local_health_context


@tool(
    "get_local_health_context",
    "Perfil epidemiológico histórico de los municipios que rodean al ciudadano (qué "
    "enfermedades se incrementaron en eventos pasados como El Niño 2023). Útil para "
    "decidir qué medicinas o kits pre-posicionar. Solo úsala si el ciudadano pregunta "
    "explícitamente por salud, kits médicos o medicinas.",
    {
        "type": "object",
        "properties": {
            "lat": {"type": "number"},
            "lon": {"type": "number"},
        },
        "required": ["lat", "lon"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def get_local_health_context(args: dict[str, Any]) -> dict[str, Any]:
    lat = float(args["lat"])
    lon = float(args["lon"])

    try:
        async with AsyncSessionLocal() as session:
            point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            q = select(Municipality).where(ST_Contains(Municipality.geometry, point))
            result = await session.execute(q)
            municipalities = list(result.scalars().all())

        if not municipalities:
            return _ok("Sin perfil epidemiológico cargado para esta zona.")

        lines = [f"**Contexto histórico de salud para ({lat:.4f}, {lon:.4f})**:"]
        for m in municipalities:
            profile = m.epi_profile or {}
            if not profile:
                lines.append(f"- {m.name}: sin perfil histórico.")
                continue
            bullets = ", ".join(f"{k}: {v}" for k, v in profile.items())
            lines.append(f"- {m.name}: {bullets}")
        return _ok("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        log.exception("get_local_health_context failed")
        return _err(f"Error consultando contexto de salud: {exc}")


# ------------------------------------------------------------- MCP server bind


hermes_server = create_sdk_mcp_server(
    name="hermes",
    version="2.0.0",
    tools=[
        get_active_alerts,
        get_my_risk,
        get_realtime_rain,
        get_nearby_pois,
        web_search,
        get_local_health_context,
    ],
)
