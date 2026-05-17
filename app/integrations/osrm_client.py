import httpx

from app.config import settings


async def get_route(
    origin: tuple[float, float],       # (lat, lon)
    destination: tuple[float, float],  # (lat, lon)
    waypoints: list[tuple[float, float]] | None = None,
) -> dict | None:
    """
    Request a driving route from OSRM.
    Accepts (lat, lon) tuples — OSRM API expects lon,lat order internally.
    Returns {geometry (GeoJSON LineString), distance_km, duration_minutes}
    or None if OSRM can't find a route.
    """
    # OSRM expects lon,lat — swap from our internal (lat, lon) convention.
    points = [origin, *(waypoints or []), destination]
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{settings.OSRM_URL}/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson"},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    return {
        "geometry": route["geometry"],         # GeoJSON LineString dict
        "distance_km": route["distance"] / 1000,
        "duration_minutes": route["duration"] / 60,
    }
