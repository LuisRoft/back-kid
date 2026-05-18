"""
GeoJSON endpoints consumed by the frontend map. All map-related endpoints live
here under the `/map` prefix.

  GET /map/corridors            → corridors monitored network (LineString)
  GET /map/risk-segments        → at-risk corridor sections
  GET /map/zones                → admin polygons with risk score per horizon
  GET /map/rain/realtime        → current precipitation samples (grid points)
  GET /map/rain/forecast        → forecasted precipitation per grid point/horizon
  GET /map/landslides/realtime  → LHASA NRT landslide events (last N hours)
  GET /map/landslides/forecast  → predicted at-risk corridor sections (alias of risk-segments)
  GET /map/pois                 → hospitals / clinics / pharmacies / supermarkets
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from geoalchemy2.shape import to_shape
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories import (
    AlertRepo,
    CorridorRepo,
    ForecastRepo,
    PoiRepo,
    RealtimeLandslideRepo,
    RealtimeRainRepo,
    RiskSegmentRepo,
    ZoneRepo,
    ZoneRiskRepo,
)
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

_POI_TYPES = {"hospital", "clinic", "pharmacy", "supermarket"}
_HORIZONS = {24, 48, 72}


def _risk_level(prob: float | None) -> tuple[str, str]:
    """Return (risk_level, hex_color) for a probability value."""
    if prob is None:
        return "none", "#22c55e"
    for threshold, level, color in _RISK_TABLE:
        if prob >= threshold:
            return level, color
    return "none", "#22c55e"


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parse `bbox=west,south,east,north` into a tuple, or None if missing."""
    if not bbox:
        return None
    try:
        parts = [float(x) for x in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(400, "bbox must be 4 comma-separated floats") from exc
    if len(parts) != 4:
        raise HTTPException(400, "bbox must be west,south,east,north")
    west, south, east, north = parts
    if west >= east or south >= north:
        raise HTTPException(400, "bbox must satisfy west<east and south<north")
    return west, south, east, north


def _default_bbox() -> tuple[float, float, float, float]:
    return settings.ecuador_bbox  # (west, south, east, north)


# --------------------------------------------------------------------- corridors


@router.get("/corridors", summary="Corridors FeatureCollection")
async def corridors_geojson(
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    corridor_repo = CorridorRepo(db)
    forecast_repo = ForecastRepo(db)
    alert_repo = AlertRepo(db)

    corridors = await corridor_repo.list_all(is_demo=is_demo)

    peak: dict[str, tuple[float, int]] = {}
    for horizon in (24, 48, 72):
        for f in await forecast_repo.list_latest_all(horizon, is_demo=is_demo):
            cid = str(f.corridor_id)
            if cid not in peak or f.probability > peak[cid][0]:
                peak[cid] = (f.probability, f.horizon_hours)

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


# ---------------------------------------------------------------- risk-segments


@router.get("/risk-segments", summary="At-risk corridor sections")
async def risk_segments_geojson(
    min_probability: Annotated[float, Query(ge=0.0, le=1.0)] = settings.RISK_THRESHOLD,
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    return await _risk_segments_payload(db, min_probability=min_probability, is_demo=is_demo)


async def _risk_segments_payload(
    db: AsyncSession, *, min_probability: float, is_demo: bool | None
) -> JSONResponse:
    segment_repo = RiskSegmentRepo(db)
    corridor_repo = CorridorRepo(db)

    segments = await segment_repo.list_active(
        is_demo=is_demo, min_probability=min_probability
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
        features.append({
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
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


# ----------------------------------------------------------------------- zones


@router.get("/zones", summary="Administrative zones with risk score")
async def zones_geojson(
    bbox: str | None = None,
    horizon: Annotated[int, Query(description="24 | 48 | 72")] = 24,
    level: str = "canton",
    db: AsyncSession = Depends(get_db),
):
    if horizon not in _HORIZONS:
        raise HTTPException(400, "horizon must be 24, 48 or 72")

    bbox_tuple = _parse_bbox(bbox)
    zone_repo = ZoneRepo(db)
    risk_repo = ZoneRiskRepo(db)

    if bbox_tuple:
        west, south, east, north = bbox_tuple
        zones = await zone_repo.list_by_bbox(
            min_lon=west, min_lat=south, max_lon=east, max_lat=north, level=level
        )
    else:
        zones = await zone_repo.list_all(level=level)

    forecasts = await risk_repo.list_active(horizon_hours=horizon)
    by_zone = {str(f.zone_id): f for f in forecasts}

    features = []
    for zone in zones:
        forecast = by_zone.get(str(zone.id))
        prob = forecast.probability if forecast else None
        level_name, color = _risk_level(prob)
        features.append({
            "type": "Feature",
            "geometry": to_shape(zone.geometry).__geo_interface__,
            "properties": {
                "id": str(zone.id),
                "code": zone.code,
                "name": zone.name,
                "level": zone.level,
                "probability": prob,
                "horizon_hours": horizon,
                "risk_level": level_name,
                "risk_color": color,
                # Breakdown — answers "why is this zone at this risk?"
                "expected_rainfall_mm": forecast.expected_rainfall_mm if forecast else None,
                "peak_susceptibility_class": forecast.peak_susceptibility_class if forecast else None,
                "computed_at": forecast.computed_at.isoformat() if forecast else None,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


# ----------------------------------------------------------------- rain realtime


@router.get("/rain/realtime", summary="Current rain samples")
async def rain_realtime_geojson(
    bbox: str | None = None,
    within_minutes: Annotated[int, Query(ge=10, le=360)] = 90,
    db: AsyncSession = Depends(get_db),
):
    west, south, east, north = _parse_bbox(bbox) or _default_bbox()
    samples = await RealtimeRainRepo(db).latest_by_bbox(
        min_lon=west,
        min_lat=south,
        max_lon=east,
        max_lat=north,
        within_minutes=within_minutes,
    )

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
            "properties": {
                "precipitation_mm_h": s.precipitation_mm_h,
                "observed_at": s.observed_at.isoformat(),
            },
        }
        for s in samples
    ]
    return JSONResponse({"type": "FeatureCollection", "features": features})


# ----------------------------------------------------------------- rain forecast


@router.get("/rain/forecast", summary="Forecasted rain by zone")
async def rain_forecast_geojson(
    bbox: str | None = None,
    horizon: Annotated[int, Query(description="24 | 48 | 72")] = 24,
    db: AsyncSession = Depends(get_db),
):
    """Currently aliased to zones with horizon — zones already aggregate
    precipitation + susceptibility into a single score, which is what the FE
    needs for the rain heatmap layer. If we later expose raw forecast samples,
    we'll split this endpoint."""
    return await zones_geojson(bbox=bbox, horizon=horizon, level="canton", db=db)


# ---------------------------------------------------------- landslides realtime


@router.get("/landslides/realtime", summary="Near-real-time landslide events")
async def landslides_realtime_geojson(
    bbox: str | None = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    db: AsyncSession = Depends(get_db),
):
    bbox_tuple = _parse_bbox(bbox)
    kwargs = {"hours": hours}
    if bbox_tuple:
        west, south, east, north = bbox_tuple
        kwargs.update(min_lon=west, min_lat=south, max_lon=east, max_lat=north)

    events = await RealtimeLandslideRepo(db).recent(**kwargs)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e.lon, e.lat]},
            "properties": {
                "severity": e.severity,
                "source": e.source,
                "reported_at": e.reported_at.isoformat(),
            },
        }
        for e in events
    ]
    return JSONResponse({"type": "FeatureCollection", "features": features})


# ---------------------------------------------------------- landslides forecast


@router.get("/landslides/forecast", summary="Predicted at-risk corridor sections")
async def landslides_forecast_geojson(
    min_probability: Annotated[float, Query(ge=0.0, le=1.0)] = settings.RISK_THRESHOLD,
    is_demo: bool | None = False,
    db: AsyncSession = Depends(get_db),
):
    """Predicted landslide layer for the map. Aliased to risk-segments so the
    FE has one canonical endpoint per concept (segment-based predictions)."""
    return await _risk_segments_payload(db, min_probability=min_probability, is_demo=is_demo)


# ------------------------------------------------------------------------ pois


@router.get("/pois", summary="POIs (hospital | clinic | pharmacy | supermarket)")
async def pois_geojson(
    bbox: str | None = None,
    types: str | None = Query(
        default=None,
        description="Comma-separated subset of: hospital,clinic,pharmacy,supermarket",
    ),
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    db: AsyncSession = Depends(get_db),
):
    west, south, east, north = _parse_bbox(bbox) or _default_bbox()
    type_filter: list[str] | None = None
    if types:
        requested = [t.strip() for t in types.split(",") if t.strip()]
        invalid = [t for t in requested if t not in _POI_TYPES]
        if invalid:
            raise HTTPException(400, f"invalid types: {invalid}. allowed: {sorted(_POI_TYPES)}")
        type_filter = requested

    pois = await PoiRepo(db).list_by_bbox_and_types(
        min_lon=west,
        min_lat=south,
        max_lon=east,
        max_lat=north,
        types=type_filter,
        limit=limit,
    )

    features = [
        {
            "type": "Feature",
            "geometry": to_shape(p.geometry).__geo_interface__,
            "properties": {
                "id": str(p.id),
                "osm_id": p.osm_id,
                "type": p.type,
                "name": p.name,
                "address": p.address,
                "source": p.source,
            },
        }
        for p in pois
    ]
    return JSONResponse({"type": "FeatureCollection", "features": features})
