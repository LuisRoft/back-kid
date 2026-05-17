import httpx

from app.config import settings


async def get_route(
    origin: tuple[float, float],       # (lat, lon)
    destination: tuple[float, float],  # (lat, lon)
) -> dict | None:
    """
    Request a driving route from OSRM.
    Accepts (lat, lon) tuples — OSRM API expects lon,lat order internally.
    Returns {geometry (GeoJSON LineString), distance_km, duration_minutes}
    or None if OSRM can't find a route.
    """
    # OSRM expects lon,lat — swap from our (lat, lon) convention
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
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
