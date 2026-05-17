"""
Baseline seed for Ecuador monitored corridors.

The corridors are real road pairs resolved through OSRM/OpenStreetMap at seed
time. Historical 2023 scores are only loaded when DEMO_MODE=true; otherwise the
same corridors are populated by the live risk pipeline.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import shape
from shapely.ops import substring
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.corridor_repo import DEMO_CORRIDOR_PREFIX
from app.db.session import AsyncSessionLocal
from app.integrations.osrm_client import get_route
from app.models.alert import Alert
from app.models.corridor import Corridor
from app.models.municipality import Municipality
from app.models.rerouting_plan import ReroutingPlan
from app.models.risk_forecast import RiskForecast
from app.models.risk_segment import RiskSegment

log = logging.getLogger(__name__)

HISTORICAL_SOURCE_NOTES = {
    "rainy_season_2023": "https://www.gestionderiesgos.gob.ec/wp-content/uploads/2023/07/INFOGRAFIA-NACIONAL-POR-LLUVIAS-21.07.2023.pdf",
    "dengue_2023": "https://www.salud.gob.ec/wp-content/uploads/2024/02/Gaceta-de-Vectoriales-SE-52.pdf",
}

_CORRIDORS: list[dict[str, Any]] = [
    {
        "key": "ec-e20-quito-santo-domingo",
        "name": "Quito-Santo Domingo E20",
        "origin": (-0.1807, -78.4678),
        "destination": (-0.2522, -79.1754),
        "population_impact": 426,
        "historical_risk": {24: 0.52, 48: 0.58, 72: 0.64},
        "historical_alert": False,
        "reroute_waypoints": [(-0.9347, -78.6155), (-1.0286, -79.4635)],
        "reroute_via": "Via Latacunga-Quevedo",
    },
    {
        "key": "ec-e25-babahoyo-guayaquil",
        "name": "Babahoyo-Guayaquil E25",
        "origin": (-1.8022, -79.5344),
        "destination": (-2.170998, -79.922359),
        "population_impact": 80_425,
        "historical_risk": {24: 0.63, 48: 0.70, 72: 0.74},
        "historical_alert": True,
        "reroute_waypoints": [(-2.1340, -79.5940), (-2.1689, -79.8357)],
        "reroute_via": "Via Milagro-Duran",
    },
    {
        "key": "ec-e25-guayaquil-machala",
        "name": "Guayaquil-Machala E25",
        "origin": (-2.170998, -79.922359),
        "destination": (-3.258111, -79.955392),
        "population_impact": 57_029,
        "historical_risk": {24: 0.57, 48: 0.62, 72: 0.68},
        "historical_alert": True,
        "reroute_waypoints": [(-2.7406, -79.6189), (-3.3250, -79.8061)],
        "reroute_via": "Via Canar-Pasaje",
    },
    {
        "key": "ec-e30-manta-portoviejo",
        "name": "Manta-Portoviejo E30",
        "origin": (-0.9677, -80.7089),
        "destination": (-1.0547, -80.4525),
        "population_impact": 72_243,
        "historical_risk": {24: 0.68, 48: 0.74, 72: 0.78},
        "historical_alert": True,
        "reroute_waypoints": [(-1.0458, -80.6589), (-0.9230, -80.4454)],
        "reroute_via": "Via Montecristi-Rocafuerte",
    },
    {
        "key": "ec-e25-santo-domingo-quevedo",
        "name": "Santo Domingo-Quevedo E25",
        "origin": (-0.2522, -79.1754),
        "destination": (-1.0286, -79.4635),
        "population_impact": 30_596,
        "historical_risk": {24: 0.55, 48: 0.61, 72: 0.67},
        "historical_alert": True,
        "reroute_waypoints": [(-0.9337, -78.6150), (-1.6612, -78.6546)],
        "reroute_via": "Via Latacunga-Riobamba",
    },
    {
        "key": "ec-e20-esmeraldas-santo-domingo",
        "name": "Esmeraldas-Santo Domingo E20",
        "origin": (0.9682, -79.6517),
        "destination": (-0.2522, -79.1754),
        "population_impact": 20_480,
        "historical_risk": {24: 0.59, 48: 0.66, 72: 0.70},
        "historical_alert": True,
        "reroute_waypoints": [(0.0836, -78.1367), (-0.1807, -78.4678)],
        "reroute_via": "Via Ibarra-Quito",
    },
    {
        "key": "ec-e582-cuenca-guayaquil",
        "name": "Cuenca-Guayaquil E582/E40",
        "origin": (-2.9006, -79.0045),
        "destination": (-2.170998, -79.922359),
        "population_impact": 55_984,
        "historical_risk": {24: 0.60, 48: 0.68, 72: 0.72},
        "historical_alert": True,
        "reroute_waypoints": [(-3.258111, -79.955392)],
        "reroute_via": "Via Pasaje-Machala",
    },
    {
        "key": "ec-e487-pallatanga-cumanda",
        "name": "Pallatanga-Cumanda E487",
        "origin": (-2.0175, -78.9736),
        "destination": (-2.2052, -79.1363),
        "population_impact": 2_774,
        "historical_risk": {24: 0.66, 48: 0.73, 72: 0.79},
        "historical_alert": True,
        "reroute_waypoints": [(-1.6612, -78.6546), (-2.2038, -79.8975)],
        "reroute_via": "Via Riobamba-Guayaquil",
    },
    {
        "key": "ec-e46-macas-riobamba",
        "name": "Macas-Riobamba E46",
        "origin": (-2.3087, -78.1114),
        "destination": (-1.6612, -78.6546),
        "population_impact": 2_943,
        "historical_risk": {24: 0.62, 48: 0.70, 72: 0.76},
        "historical_alert": True,
        "reroute_waypoints": [(-2.9006, -79.0045)],
        "reroute_via": "Via Cuenca",
    },
    {
        "key": "ec-e45-el-chaco-reventador",
        "name": "El Chaco-Reventador E45",
        "origin": (-0.3399, -77.8107),
        "destination": (-0.0753, -77.6556),
        "population_impact": 233,
        "historical_risk": {24: 0.58, 48: 0.66, 72: 0.73},
        "historical_alert": True,
        "reroute_waypoints": [(0.0840, -76.8844), (-0.4629, -76.9872)],
        "reroute_via": "Via Lago Agrio-Coca",
    },
]

_MUNICIPALITIES: list[dict[str, Any]] = [
    {
        "name": "Esmeraldas",
        "wkt": "MULTIPOLYGON(((-80.3 0.5, -79.1 0.5, -79.1 1.5, -80.3 1.5, -80.3 0.5)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 1742,
            "diarrhea_risk": "high",
            "vulnerable_population": 20480,
        },
    },
    {
        "name": "Manabi",
        "wkt": "MULTIPOLYGON(((-80.9 -1.8, -79.7 -1.8, -79.7 -0.2, -80.9 -0.2, -80.9 -1.8)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 7355,
            "diarrhea_risk": "high",
            "vulnerable_population": 72243,
        },
    },
    {
        "name": "Guayas",
        "wkt": "MULTIPOLYGON(((-80.4 -2.8, -79.2 -2.8, -79.2 -1.5, -80.4 -1.5, -80.4 -2.8)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 3059,
            "diarrhea_risk": "high",
            "vulnerable_population": 47551,
        },
    },
    {
        "name": "Los Rios",
        "wkt": "MULTIPOLYGON(((-80.0 -2.2, -79.2 -2.2, -79.2 -0.9, -80.0 -0.9, -80.0 -2.2)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 794,
            "diarrhea_risk": "critical",
            "vulnerable_population": 32874,
        },
    },
    {
        "name": "El Oro",
        "wkt": "MULTIPOLYGON(((-80.3 -3.9, -79.4 -3.9, -79.4 -2.8, -80.3 -2.8, -80.3 -3.9)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 6312,
            "diarrhea_risk": "medium",
            "vulnerable_population": 1102,
        },
    },
    {
        "name": "Chimborazo",
        "wkt": "MULTIPOLYGON(((-79.1 -2.4, -78.2 -2.4, -78.2 -1.3, -79.1 -1.3, -79.1 -2.4)))",
        "epi_profile": {
            "source_period": "Rainy season 2023",
            "dengue_2023_cases": 7,
            "diarrhea_risk": "medium",
            "vulnerable_population": 2774,
        },
    },
]


async def run_seed_demo() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await _seed(session)
            await session.commit()
            log.info("Baseline seed complete")
        except Exception:
            await session.rollback()
            log.exception("Baseline seed failed; rolled back")
            raise


async def _seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    await _seed_municipalities(session)

    seeded = 0
    for record in _CORRIDORS:
        corridor = await _get_corridor_by_key(session, record["key"])
        if corridor is None:
            route = await _fetch_osrm_route(record)
            corridor = Corridor(
                name=record["name"],
                geometry=WKTElement(_route_wkt(route), srid=4326),
                population_impact=record["population_impact"],
                country="EC",
                osm_id=record["key"],
                is_demo=False,
            )
            session.add(corridor)
            await session.flush()
            seeded += 1

        await _seed_rerouting_plan(session, corridor, record)

        if settings.DEMO_MODE:
            demo_corridor = await _seed_demo_corridor(session, corridor, record)
            await _seed_rerouting_plan(session, demo_corridor, record)
            await _seed_historical_forecasts(session, demo_corridor, record, now)
            await _seed_historical_segments(session, demo_corridor, record, now)

    await session.flush()
    log.info("Seeded %d new real corridors; monitored total target=%d", seeded, len(_CORRIDORS))


async def _seed_municipalities(session: AsyncSession) -> None:
    for record in _MUNICIPALITIES:
        existing = await session.execute(
            select(Municipality).where(Municipality.name == record["name"]).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        session.add(
            Municipality(
                name=record["name"],
                geometry=WKTElement(record["wkt"], srid=4326),
                country="EC",
                epi_profile=record["epi_profile"],
            )
        )


async def _get_corridor_by_key(session: AsyncSession, key: str) -> Corridor | None:
    result = await session.execute(select(Corridor).where(Corridor.osm_id == key).limit(1))
    return result.scalar_one_or_none()


async def _seed_demo_corridor(
    session: AsyncSession,
    live_corridor: Corridor,
    record: dict[str, Any],
) -> Corridor:
    demo_key = f"{DEMO_CORRIDOR_PREFIX}{record['key']}"
    existing = await _get_corridor_by_key(session, demo_key)
    if existing is not None:
        return existing

    demo_corridor = Corridor(
        name=record["name"],
        geometry=WKTElement(to_shape(live_corridor.geometry).wkt, srid=4326),
        population_impact=record["population_impact"],
        country="EC",
        osm_id=demo_key,
        is_demo=True,
    )
    session.add(demo_corridor)
    await session.flush()
    return demo_corridor


async def _fetch_osrm_route(record: dict[str, Any]) -> dict:
    route = await get_route(record["origin"], record["destination"])
    if route is None:
        raise RuntimeError(f"OSRM could not resolve monitored corridor {record['name']}")
    return route


def _route_wkt(route: dict) -> str:
    geom = shape(route["geometry"])
    simplified = geom.simplify(0.0015, preserve_topology=False)
    return simplified.wkt


async def _seed_rerouting_plan(
    session: AsyncSession,
    corridor: Corridor,
    record: dict[str, Any],
) -> None:
    existing = await session.execute(
        select(ReroutingPlan).where(ReroutingPlan.corridor_id == corridor.id).limit(1)
    )
    if existing.scalar_one_or_none():
        return

    waypoints = record.get("reroute_waypoints") or []
    if not waypoints:
        return

    route = await get_route(record["origin"], record["destination"], waypoints=waypoints)
    if route is None:
        log.warning("OSRM could not resolve rerouting plan for %s", record["name"])
        return

    session.add(
        ReroutingPlan(
            corridor_id=corridor.id,
            geometry=WKTElement(_route_wkt(route), srid=4326),
            distance_km=route["distance_km"],
            duration_minutes=route["duration_minutes"],
            via_description=record["reroute_via"],
            computed_at=datetime.now(timezone.utc),
        )
    )


async def _seed_historical_forecasts(
    session: AsyncSession,
    corridor: Corridor,
    record: dict[str, Any],
    now: datetime,
) -> None:
    existing = await session.execute(
        select(RiskForecast)
        .where(RiskForecast.corridor_id == corridor.id, RiskForecast.is_demo == True)  # noqa: E712
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return

    for horizon, prob in record["historical_risk"].items():
        session.add(
            RiskForecast(
                corridor_id=corridor.id,
                horizon_hours=horizon,
                probability=prob,
                computed_at=now,
                valid_from=now + timedelta(hours=horizon - 24),
                is_demo=True,
            )
        )

    peak_horizon = max(record["historical_risk"], key=record["historical_risk"].get)
    peak_prob = record["historical_risk"][peak_horizon]
    if record["historical_alert"] and peak_prob >= settings.RISK_THRESHOLD:
        session.add(
            Alert(
                corridor_id=corridor.id,
                probability=peak_prob,
                horizon_hours=peak_horizon,
                generated_at=now,
                is_active=True,
                is_demo=True,
            )
        )


async def _seed_historical_segments(
    session: AsyncSession,
    corridor: Corridor,
    record: dict[str, Any],
    now: datetime,
) -> None:
    existing = await session.execute(
        select(RiskSegment)
        .where(RiskSegment.corridor_id == corridor.id, RiskSegment.is_demo == True)  # noqa: E712
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return

    line = to_shape(corridor.geometry)
    segment_count = max(settings.RISK_SEGMENT_COUNT, 1)
    hotspot_index = _stable_hotspot_index(record["key"], segment_count)
    start = line.length * hotspot_index / segment_count
    end = line.length * (hotspot_index + 1) / segment_count
    hotspot = substring(line, start, end)
    if hotspot.is_empty or hotspot.length == 0:
        hotspot = line

    for horizon, probability in record["historical_risk"].items():
        if probability < 0.20:
            continue
        session.add(
            RiskSegment(
                corridor_id=corridor.id,
                geometry=WKTElement(hotspot.wkt, srid=4326),
                segment_index=hotspot_index,
                horizon_hours=horizon,
                probability=probability,
                susceptibility_class=4 if probability >= settings.RISK_THRESHOLD else 3,
                computed_at=now,
                valid_from=now + timedelta(hours=horizon - 24),
                is_active=True,
                is_demo=True,
            )
        )


def _stable_hotspot_index(key: str, segment_count: int) -> int:
    return sum(ord(char) for char in key) % segment_count
