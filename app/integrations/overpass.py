"""OSM Overpass API client — fetches POIs (hospitals, clinics, pharmacies, supermarkets).

This is the single source for the map's POI layer. Albergues and humanitarian
aid are NOT queried here — the agent resolves those on-demand via Tavily.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx

log = logging.getLogger(__name__)

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
# Overpass returns 406 if no User-Agent is set; identify ourselves politely.
_USER_AGENT = "back-kid/0.1 (https://github.com/LuisRoft/back-kid)"

# Internal POI category -> Overpass key/value pairs to match.
CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "hospital": [("amenity", "hospital")],
    "clinic": [("amenity", "clinic"), ("amenity", "doctors")],
    "pharmacy": [("amenity", "pharmacy")],
    "supermarket": [("shop", "supermarket")],
}


class OverpassError(RuntimeError):
    pass


def _build_query(
    *,
    bbox: tuple[float, float, float, float],
    categories: Iterable[str],
    timeout_s: int = 60,
) -> str:
    """Build an Overpass QL query for the given bbox and categories.

    bbox is (south, west, north, east) per Overpass conventions.
    """
    south, west, north, east = bbox
    blocks: list[str] = []
    for cat in categories:
        for key, value in CATEGORY_TAGS.get(cat, []):
            blocks.append(f'  node["{key}"="{value}"]({south},{west},{north},{east});')
            blocks.append(f'  way["{key}"="{value}"]({south},{west},{north},{east});')

    if not blocks:
        raise OverpassError("No valid Overpass categories provided")

    body = "\n".join(blocks)
    return f"""[out:json][timeout:{timeout_s}];
(
{body}
);
out center tags;
"""


async def fetch_pois(
    *,
    bbox: tuple[float, float, float, float],
    categories: list[str],
) -> list[dict]:
    """Run the Overpass query and return normalized POI records.

    Each returned record has:
        osm_id, type, name, address, lat, lon
    """
    valid_cats = [c for c in categories if c in CATEGORY_TAGS]
    if not valid_cats:
        return []

    query = _build_query(bbox=bbox, categories=valid_cats)

    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=90.0, headers=headers) as client:
        for attempt in range(3):
            try:
                r = await client.post(
                    OVERPASS_ENDPOINT,
                    content=query.encode("utf-8"),
                    headers={"Content-Type": "text/plain"},
                )
                r.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 504) and attempt < 2:
                    await asyncio.sleep(5.0 * (attempt + 1))
                    continue
                raise OverpassError(
                    f"Overpass upstream error {exc.response.status_code}: {exc.response.text[:200]}"
                ) from exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == 2:
                    raise OverpassError(f"Overpass transport error: {exc}") from exc
                await asyncio.sleep(2.0 * (attempt + 1))

    data = r.json()
    return list(_normalize(data.get("elements") or []))


def _normalize(elements: list[dict]) -> Iterable[dict]:
    for el in elements:
        tags = el.get("tags") or {}
        poi_type = _classify(tags)
        if poi_type is None:
            continue

        if el.get("type") == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:  # way / relation — Overpass returns a `center` block when out center is used
            center = el.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        yield {
            "osm_id": f'{el.get("type", "node")}/{el.get("id")}',
            "type": poi_type,
            "name": tags.get("name"),
            "address": _address(tags),
            "lat": float(lat),
            "lon": float(lon),
        }


def _classify(tags: dict[str, str]) -> str | None:
    if tags.get("amenity") == "hospital":
        return "hospital"
    if tags.get("amenity") in ("clinic", "doctors"):
        return "clinic"
    if tags.get("amenity") == "pharmacy":
        return "pharmacy"
    if tags.get("shop") == "supermarket":
        return "supermarket"
    return None


def _address(tags: dict[str, str]) -> str | None:
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:city"),
    ]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None
