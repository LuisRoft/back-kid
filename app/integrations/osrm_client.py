import httpx

from app.config import settings


async def get_route(
    origin: tuple[float, float],       # (lon, lat)
    destination: tuple[float, float],  # (lon, lat)
) -> dict | None:
    """
    Request a driving route from OSRM.
    Returns {geometry (GeoJSON LineString), distance_km, duration_minutes}
    or None if OSRM can't find a route.
    """
    coords = f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
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
