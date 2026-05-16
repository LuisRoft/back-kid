import httpx

from app.config import settings


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
    Sum precipitation over the next 24 / 48 / 72 hours.
    Returns (mm_24h, mm_48h, mm_72h).
    """
    hourly = forecast.get("hourly", {}).get("precipitation", [])
    mm_24 = sum(hourly[:24])
    mm_48 = sum(hourly[:48])
    mm_72 = sum(hourly[:72])
    return mm_24, mm_48, mm_72
