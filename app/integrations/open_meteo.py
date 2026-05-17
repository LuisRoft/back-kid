import asyncio
import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def get_precipitation_forecast(lat: float, lon: float) -> dict:
    """Hourly precipitation (mm) for next 72 h at the given point."""
    return (await get_precipitation_forecasts([(lat, lon)]))[0]


async def get_precipitation_forecasts(points: list[tuple[float, float]]) -> list[dict]:
    """Hourly precipitation (mm) for next 72 h at one or more points."""
    params = {
        "latitude": ",".join(str(lat) for lat, _ in points),
        "longitude": ",".join(str(lon) for _, lon in points),
        "hourly": "precipitation",
        "forecast_days": 3,
        "timezone": "America/Guayaquil",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        for attempt in range(3):
            try:
                r = await client.get(f"{settings.OPEN_METEO_URL}/v1/forecast", params=params)
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, list) else [data]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt == 2:
                    raise
                await asyncio.sleep(2.0 * (attempt + 1))
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))


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
