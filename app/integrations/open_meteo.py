import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def get_precipitation_forecast(lat: float, lon: float) -> dict:
    """Hourly precipitation (mm) for next 72 h at the given point."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{settings.OPEN_METEO_URL}/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "forecast_days": 3,
                "timezone": "America/Guayaquil",
            },
        )
        r.raise_for_status()
        return r.json()


def aggregate_precipitation(forecast: dict) -> tuple[float, float, float]:
    """
    Sum precipitation per window (not cumulative).
    Returns (mm_24h, mm_48h, mm_72h) where each value is the total
    for that specific 24-hour window, not the running total.
    Open-Meteo can return None for missing data points — treated as 0.
    """
    hourly = forecast.get("hourly", {}).get("precipitation", [])
    vals = [v if v is not None else 0.0 for v in hourly]
    if len(vals) < 72:
        log.warning("Open-Meteo returned %d hourly values (expected ≥72) — padding with zeros", len(vals))
        vals.extend([0.0] * (72 - len(vals)))
    mm_24 = sum(vals[:24])        # hours  0–23
    mm_48 = sum(vals[24:48])      # hours 24–47
    mm_72 = sum(vals[48:72])      # hours 48–71
    return mm_24, mm_48, mm_72
