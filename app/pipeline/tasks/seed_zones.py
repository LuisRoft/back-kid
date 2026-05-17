"""Seed Ecuador administrative zones (cantons / parroquias) into the `zones` table.

Reads a GeoJSON file from `data/seed/`. The file is expected to contain a
FeatureCollection where each feature has properties:
  - code  (string, unique within level)
  - name  (string)
  - level ('canton' | 'parroquia')

A bundled or manually downloaded GeoJSON is preferred over fetching at runtime
(deterministic for the demo, no network dependency at startup).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from geoalchemy2 import WKTElement
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.zone import Zone

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "seed"
ZONE_FILES = [
    ("canton", DATA_DIR / "ecuador_cantons.geojson"),
    ("parroquia", DATA_DIR / "ecuador_parroquias.geojson"),
]


async def run_seed_zones() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await _seed(session)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("Zone seed failed; rolled back")
            raise


async def _seed(session: AsyncSession) -> None:
    total = 0
    for level, path in ZONE_FILES:
        if not path.exists():
            log.warning(
                "Zone seed file missing for level=%s at %s — skipping. "
                "Drop a FeatureCollection with {code, name} properties to enable.",
                level,
                path,
            )
            continue

        with path.open("r", encoding="utf-8") as fh:
            collection = json.load(fh)

        inserted = await _seed_collection(session, level=level, collection=collection)
        total += inserted
        log.info("Seeded %d zones at level=%s from %s", inserted, level, path.name)

    if total:
        log.info("Zone seed complete (%d new rows)", total)


async def _seed_collection(
    session: AsyncSession, *, level: str, collection: dict
) -> int:
    features = collection.get("features") or []
    if not features:
        return 0

    existing_codes = await _existing_codes(session, level=level)

    inserted = 0
    for feature in features:
        props = feature.get("properties") or {}
        # Accept several common key conventions: our canonical `code`/`name`,
        # INEC's `DPA_*`, and GADM's `GID_2`/`NAME_2` (canton) / `GID_3`/`NAME_3` (parroquia).
        code = (
            props.get("code")
            or props.get("DPA_CANTON")
            or props.get("DPA_PARROQ")
            or props.get("GID_2")
            or props.get("GID_3")
        )
        name = (
            props.get("name")
            or props.get("DPA_DESCAN")
            or props.get("DPA_DESPAR")
            or props.get("NAME_2")
            or props.get("NAME_3")
        )
        if not code or not name:
            continue
        code = str(code)
        if code in existing_codes:
            continue

        try:
            geom = shape(feature["geometry"])
        except (KeyError, ValueError):
            log.warning("Skipping zone with invalid geometry: code=%s", code)
            continue

        # Normalize to MULTIPOLYGON
        if geom.geom_type == "Polygon":
            from shapely.geometry import MultiPolygon

            geom = MultiPolygon([geom])
        if geom.geom_type != "MultiPolygon":
            log.warning(
                "Skipping zone with non-polygonal geometry: code=%s type=%s",
                code,
                geom.geom_type,
            )
            continue

        session.add(
            Zone(
                code=code,
                name=str(name),
                level=level,
                country="EC",
                geometry=WKTElement(geom.wkt, srid=4326),
            )
        )
        existing_codes.add(code)
        inserted += 1

    if inserted:
        await session.flush()
    return inserted


async def _existing_codes(session: AsyncSession, *, level: str) -> set[str]:
    result = await session.execute(select(Zone.code).where(Zone.level == level))
    return {row for row in result.scalars().all()}
