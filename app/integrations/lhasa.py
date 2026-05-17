"""NASA LHASA near-real-time landslide events.

The official LHASA NRT product is delivered as a NetCDF on a daily cadence with
~24 h latency. For the MVP we synthesize near-real-time events using the
in-memory LHASA susceptibility raster (loaded at startup) combined with very
recent precipitation samples — wherever susceptibility is HIGH and rain in the
last hour has been HEAVY, we emit a moderate/high-severity event.

This is a pragmatic stand-in until the LHASA NRT pipeline (true NetCDF feed)
is wired in. The interface is stable: callers receive `EventDict`s and don't
need to know the source.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TypedDict

from app.pipeline.processors import susceptibility as susc_mod

log = logging.getLogger(__name__)

# Tuning thresholds for the heuristic fallback.
HIGH_SUSCEPTIBILITY = 4          # LHASA classes 0–5; >=4 is the upper band
RAIN_HEAVY_MM_PER_HOUR = 5.0     # ~heavy short-window precipitation
RAIN_EXTREME_MM_PER_HOUR = 12.0  # ~extreme — promotes severity to 'high'


class EventDict(TypedDict):
    lat: float
    lon: float
    severity: str  # 'low' | 'moderate' | 'high'
    reported_at: datetime
    source: str


def synthesize_events_from_rain(
    rain_samples: list[tuple[float, float, float, datetime]],
) -> list[EventDict]:
    """Build events from recent rain samples + the susceptibility raster.

    Each input tuple is (lat, lon, precipitation_mm_h, observed_at).
    """
    events: list[EventDict] = []
    for lat, lon, mm_h, observed_at in rain_samples:
        if mm_h < RAIN_HEAVY_MM_PER_HOUR:
            continue
        susceptibility = susc_mod.get_susceptibility(lat, lon)
        if susceptibility < HIGH_SUSCEPTIBILITY:
            continue

        severity = "high" if mm_h >= RAIN_EXTREME_MM_PER_HOUR else "moderate"
        events.append(
            EventDict(
                lat=lat,
                lon=lon,
                severity=severity,
                reported_at=observed_at,
                source="lhasa-nrt",
            )
        )
    log.info(
        "LHASA-NRT (synthesized) emitted %d events from %d rain samples",
        len(events),
        len(rain_samples),
    )
    return events


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
