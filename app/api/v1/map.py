"""
GeoJSON endpoints consumed directly by Mapbox GL JS.

  GET /map/corridors       → FeatureCollection of monitored corridors, colored by risk
  GET /map/rerouting-plans → FeatureCollection of alternate routes for alerted corridors
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from geoalchemy2.shape import to_shape
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import AlertRepo, CorridorRepo, ForecastRepo, ReroutingPlanRepo
from app.dependencies import get_db

router = APIRouter(prefix="/map", tags=["map"])

# Ordered highest → lowest so the first match wins
_RISK_TABLE = [
    (0.85, "critical", "#7f1d1d"),
    (0.65, "high",     "#ef4444"),
    (0.45, "moderate", "#f97316"),
    (0.20, "low",      "#eab308"),
    (0.0,  "none",     "#22c55e"),
]


def _risk_level(prob: float | None) -> tuple[str, str]:
    """Return (risk_level, hex_color) for a probability value."""
    if prob is None:
        return "none", "#22c55e"
    for threshold, level, color in _RISK_TABLE:
        if prob >= threshold:
            return level, color
    return "none", "#22c55e"


@router.get("/corridors", summary="Corridors FeatureCollection for Mapbox")
async def corridors_geojson(
    is_demo: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a GeoJSON FeatureCollection. Each feature is a monitored corridor
    (LineString) with risk metadata as properties ready for Mapbox paint expressions.

    Use directly with:
        map.addSource('corridors', { type: 'geojson', data: <this endpoint> })
    """
    corridor_repo = CorridorRepo(db)
    forecast_repo = ForecastRepo(db)
    alert_repo = AlertRepo(db)

    corridors = await corridor_repo.list_all(is_demo=is_demo)

    # Peak probability across all 3 horizons per corridor
    peak: dict[str, tuple[float, int]] = {}
    for horizon in (24, 48, 72):
        for f in await forecast_repo.list_latest_all(horizon, is_demo=is_demo):
            cid = str(f.corridor_id)
            if cid not in peak or f.probability > peak[cid][0]:
                peak[cid] = (f.probability, f.horizon_hours)

    # Which corridors have an active alert right now
    alerted_ids = {
        str(a.corridor_id)
        for a in await alert_repo.list_active(is_demo=is_demo)
    }

    features = []
    for corridor in corridors:
        cid = str(corridor.id)
        prob, horizon = peak.get(cid, (None, None))
        level, color = _risk_level(prob)

        features.append({
            "type": "Feature",
            "geometry": to_shape(corridor.geometry).__geo_interface__,
            "properties": {
                "id": cid,
                "name": corridor.name,
                "probability": prob,
                "horizon_hours": horizon,
                "risk_level": level,       # "none"|"low"|"moderate"|"high"|"critical"
                "risk_color": color,        # hex — use directly in Mapbox paint
                "alert_active": cid in alerted_ids,
                "population_impact": corridor.population_impact,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@router.get("/rerouting-plans", summary="Alternate routes FeatureCollection for Mapbox")
async def rerouting_plans_geojson(
    is_demo: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a GeoJSON FeatureCollection of alternate routes.
    Only corridors with an active alert have a rerouting plan shown.

    Use directly with:
        map.addSource('rerouting', { type: 'geojson', data: <this endpoint> })
    """
    alert_repo = AlertRepo(db)
    corridor_repo = CorridorRepo(db)
    plan_repo = ReroutingPlanRepo(db)

    active_alerts = await alert_repo.list_active(is_demo=is_demo)
    if not active_alerts:
        return JSONResponse({"type": "FeatureCollection", "features": []})

    alerted_corridor_ids = list({a.corridor_id for a in active_alerts})

    corridor_map = {c.id: c for c in await corridor_repo.list_all(is_demo=is_demo)}
    plans = await plan_repo.list_for_corridors(alerted_corridor_ids)

    features = []
    for plan in plans:
        corridor = corridor_map.get(plan.corridor_id)
        features.append({
            "type": "Feature",
            "geometry": to_shape(plan.geometry).__geo_interface__,
            "properties": {
                "corridor_id": str(plan.corridor_id),
                "corridor_name": corridor.name if corridor else "",
                "distance_km": plan.distance_km,
                "duration_minutes": plan.duration_minutes,
                "via_description": plan.via_description,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})
