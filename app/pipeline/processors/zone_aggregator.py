"""Aggregate landslide risk by administrative zone.

For each zone, sample a small set of interior points (the centroid + a coarse
grid clipped to the polygon), feed them through the same precipitation +
susceptibility model used for corridors, and take the peak probability per
horizon as the zone score.
"""
from __future__ import annotations

import logging

from geoalchemy2.shape import to_shape
from shapely.geometry import MultiPolygon, Point, Polygon

from app.pipeline.processors.risk_scorer import compute_probabilities
from app.pipeline.processors.susceptibility import get_susceptibility

log = logging.getLogger(__name__)


def sample_points_for_zone(geom_wkb, *, target_points: int = 6) -> list[tuple[float, float]]:
    """Pick a few interior points inside the zone (lat, lon)."""
    shape = to_shape(geom_wkb)
    if not isinstance(shape, (Polygon, MultiPolygon)):
        return []

    minx, miny, maxx, maxy = shape.bounds
    if minx == maxx or miny == maxy:
        c = shape.centroid
        return [(c.y, c.x)]

    # Pick a 3x3 grid of candidates over the bbox and keep those inside.
    candidates: list[tuple[float, float]] = []
    steps = 3
    for i in range(steps):
        for j in range(steps):
            lon = minx + (maxx - minx) * (i + 0.5) / steps
            lat = miny + (maxy - miny) * (j + 0.5) / steps
            if shape.contains(Point(lon, lat)):
                candidates.append((lat, lon))

    if not candidates:
        c = shape.centroid
        return [(c.y, c.x)]

    if len(candidates) > target_points:
        # Evenly down-sample
        stride = max(len(candidates) // target_points, 1)
        candidates = candidates[::stride][:target_points]
    return candidates


def aggregate_zone_probabilities(
    sample_precipitation: list[tuple[float, float, float]],
    points: list[tuple[float, float]],
) -> dict[int, float]:
    """Peak (mm_24, mm_48, mm_72, susceptibility) → {horizon: probability}.

    `sample_precipitation` is one (mm_24, mm_48, mm_72) tuple per point.
    """
    peaks: dict[int, float] = {24: 0.02, 48: 0.02, 72: 0.02}
    for (lat, lon), (mm_24, mm_48, mm_72) in zip(points, sample_precipitation, strict=False):
        susceptibility = get_susceptibility(lat, lon)
        probs = compute_probabilities(mm_24, mm_48, mm_72, susceptibility_class=susceptibility)
        for horizon, value in probs.items():
            if value > peaks[horizon]:
                peaks[horizon] = value
    return peaks
