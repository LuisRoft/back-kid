"""POIs refresh task — fetches hospitals, clinics, pharmacies and supermarkets
from OSM Overpass and upserts them into the `pois` table.

Runs at startup and weekly thereafter. The map endpoint reads straight from the
table, so this is the only path that talks to Overpass.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings
from app.db.repositories.poi_repo import PoiRepo
from app.db.session import AsyncSessionLocal
from app.integrations.overpass import OverpassError, fetch_pois

log = logging.getLogger(__name__)

POI_CATEGORIES = ["hospital", "clinic", "pharmacy", "supermarket"]


async def run_pois_refresh_task() -> None:
    log.info("POIs refresh task started")
    west, south, east, north = settings.ecuador_bbox
    # Overpass expects (south, west, north, east).
    bbox = (south, west, north, east)
    try:
        records = await fetch_pois(bbox=bbox, categories=POI_CATEGORIES)
    except OverpassError as exc:
        log.error("Overpass fetch failed: %s", exc)
        return

    if not records:
        log.warning("Overpass returned 0 POIs — nothing to upsert")
        return

    rows = [_to_upsert_row(record) for record in records]

    async with AsyncSessionLocal() as session:
        try:
            inserted = await PoiRepo(session).upsert_from_osm(rows)
            await session.commit()
            log.info("POIs refresh upserted %d rows", inserted)
        except Exception:
            await session.rollback()
            log.exception("POIs refresh failed — rolled back")
            raise


def _to_upsert_row(record: dict) -> dict:
    return {
        "osm_id": record["osm_id"],
        "type": record["type"],
        "name": record.get("name"),
        "address": record.get("address"),
        "source": "osm",
        "geometry": f"SRID=4326;POINT({record['lon']} {record['lat']})",
        "fetched_at": datetime.now(timezone.utc),
    }
