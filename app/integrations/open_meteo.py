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


# Open-Meteo's URL has a hard length limit (~8 KB). At ~10 chars per coord, this
# caps a single multi-point request to ~80–100 points safely.
_GRID_CHUNK_SIZE = 80


async def get_current_precipitation_grid(
    points: list[tuple[float, float]],
) -> list[dict]:
    """Current precipitation (mm/h) at one or more points.

    Open-Meteo accepts multi-point forecasts via comma-separated lat/lon, but
    the URL length is limited. We chunk the input to stay under the limit and
    concatenate the per-chunk responses in input order.
    """
    if not points:
        return []

    results: list[dict] = []
    failed = 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        chunks = [
            points[i : i + _GRID_CHUNK_SIZE]
            for i in range(0, len(points), _GRID_CHUNK_SIZE)
        ]
        for index, chunk in enumerate(chunks):
            if index > 0:
                # Open-Meteo free tier rate-limits per-minute; space out chunks.
                await asyncio.sleep(1.5)
            try:
                chunk_results = await _fetch_current_chunk(client, chunk)
                results.extend(chunk_results)
            except httpx.HTTPStatusError as exc:
                # Don't fail the whole run for transient errors on a single chunk —
                # log and keep going. A partial sample set is more useful than none.
                failed += 1
                log.warning(
                    "Chunk %d/%d failed (%s) — continuing with partial results",
                    index + 1, len(chunks), exc.response.status_code,
                )
    if failed:
        log.info(
            "Current grid completed with %d/%d chunks failed (%d points OK)",
            failed, len(chunks), len(results),
        )
    return results


async def _fetch_current_chunk(
    client: httpx.AsyncClient, points: list[tuple[float, float]]
) -> list[dict]:
    params = {
        "latitude": ",".join(str(lat) for lat, _ in points),
        "longitude": ",".join(str(lon) for _, lon in points),
        "current": "precipitation,rain",
        # Force UTC so the `current.time` we store matches the timezone we
        # tag it with — otherwise samples appear 5h old and `within_minutes`
        # filters them out.
        "timezone": "GMT",
    }
    for attempt in range(3):
        try:
            r = await client.get(f"{settings.OPEN_METEO_URL}/v1/forecast", params=params)
            r.raise_for_status()
            data = r.json()
            # Single point → dict; multiple → list. Normalize to list.
            if isinstance(data, list):
                return data
            return [data]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == 2:
                raise
            await asyncio.sleep(2.0 * (attempt + 1))
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == 2:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    return []


def build_national_grid(
    bbox: tuple[float, float, float, float],
    step_deg: float,
) -> list[tuple[float, float]]:
    """Build a (lat, lon) grid covering the given bbox.

    bbox is (west, south, east, north). step_deg controls density.
    """
    west, south, east, north = bbox
    if step_deg <= 0:
        raise ValueError("step_deg must be > 0")

    points: list[tuple[float, float]] = []
    lat = south
    while lat <= north + 1e-9:
        lon = west
        while lon <= east + 1e-9:
            points.append((round(lat, 4), round(lon, 4)))
            lon += step_deg
        lat += step_deg
    return points


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
