"""
GeoJSON endpoints consumed directly by Mapbox GL JS.

  GET /map/corridors       → FeatureCollection of monitored corridors
  GET /map/risk-segments   → FeatureCollection of at-risk corridor sections
  GET /map/rerouting-plans → FeatureCollection of alternate routes for alerted corridors
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from geoalchemy2.shape import to_shape
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories import AlertRepo, CorridorRepo, ForecastRepo, ReroutingPlanRepo, RiskSegmentRepo
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
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a GeoJSON FeatureCollection. Each feature is a monitored corridor
    (LineString). Use /map/risk-segments for red/orange risk styling.

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
                "risk_level": "monitored",
                "risk_color": "#64748b",
                "peak_risk_level": level,
                "peak_risk_color": color,
                "alert_active": cid in alerted_ids,
                "population_impact": corridor.population_impact,
                "is_demo": corridor.is_demo,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@router.get("/rerouting-plans", summary="Alternate routes FeatureCollection for Mapbox")
async def rerouting_plans_geojson(
    is_demo: bool | None = False,
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


@router.get("/risk-segments", summary="At-risk corridor sections FeatureCollection for Mapbox")
async def risk_segments_geojson(
    min_probability: Annotated[float, Query(ge=0.0, le=1.0)] = settings.RISK_THRESHOLD,
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns only the specific road sections currently carrying risk.
    Use this layer for red/orange danger styling; keep /map/corridors as the
    neutral monitored network.
    """
    segment_repo = RiskSegmentRepo(db)
    corridor_repo = CorridorRepo(db)

    segments = await segment_repo.list_active(
        is_demo=is_demo,
        min_probability=min_probability,
    )
    corridors = {c.id: c for c in await corridor_repo.list_all(is_demo=is_demo)}

    peaks = {}
    for segment in segments:
        key = (segment.corridor_id, segment.segment_index)
        if key not in peaks or segment.probability > peaks[key].probability:
            peaks[key] = segment

    features = []
    for segment in peaks.values():
        corridor = corridors.get(segment.corridor_id)
        level, color = _risk_level(segment.probability)
        features.append(
            {
                "type": "Feature",
                "geometry": to_shape(segment.geometry).__geo_interface__,
                "properties": {
                    "id": segment.id,
                    "corridor_id": str(segment.corridor_id),
                    "corridor_name": corridor.name if corridor else "",
                    "segment_index": segment.segment_index,
                    "probability": segment.probability,
                    "horizon_hours": segment.horizon_hours,
                    "risk_level": level,
                    "risk_color": color,
                    "susceptibility_class": segment.susceptibility_class,
                    "computed_at": segment.computed_at.isoformat(),
                    "valid_from": segment.valid_from.isoformat(),
                    "is_demo": segment.is_demo,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})
