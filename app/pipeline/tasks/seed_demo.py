"""
Demo seed — populates the DB with El Niño 2023 Ecuador scenario data.
Idempotent: skips if is_demo rows already exist.
"""
import logging
from datetime import datetime, timedelta, timezone

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert
from app.models.corridor import Corridor
from app.models.municipality import Municipality
from app.models.rerouting_plan import ReroutingPlan
from app.models.risk_forecast import RiskForecast

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static demo data — El Niño 2023 Ecuador
# ---------------------------------------------------------------------------

_CORRIDORS = [
    {
        "name": "Panamericana Norte E35 (Quito–Ibarra)",
        "wkt": "LINESTRING(-78.5161 -0.2149, -78.4892 -0.0498, -78.3461 0.0587, -78.1166 0.3513)",
        "population_impact": 280_000,
        "osm_id": "w23645001",
        # Moderate risk — Andean route, less exposed to coastal rainfall
        "risks": {24: 0.42, 48: 0.51, 72: 0.58},
        "alert": False,
    },
    {
        "name": "Guayaquil–Machala E25",
        "wkt": "LINESTRING(-79.8975 -2.1709, -79.9200 -2.5000, -79.9411 -3.0000, -79.9542 -3.2581)",
        "population_impact": 650_000,
        "osm_id": "w48123002",
        # HIGH risk — coastal, direct El Niño impact
        "risks": {24: 0.81, 48: 0.88, 72: 0.91},
        "alert": True,
    },
    {
        "name": "Quito–Santo Domingo E28",
        "wkt": "LINESTRING(-78.5161 -0.2149, -78.8500 -0.2000, -79.0000 -0.2300, -79.1734 -0.2520)",
        "population_impact": 420_000,
        "osm_id": "w31987003",
        # HIGH risk — descends into coastal lowlands
        "risks": {24: 0.74, 48: 0.82, 72: 0.87},
        "alert": True,
    },
    {
        "name": "Latacunga–Riobamba E35 Sur",
        "wkt": "LINESTRING(-78.6169 -0.9302, -78.6300 -1.2000, -78.6496 -1.6714)",
        "population_impact": 180_000,
        "osm_id": "w19234004",
        # Moderate risk
        "risks": {24: 0.38, 48: 0.46, 72: 0.53},
        "alert": False,
    },
    {
        "name": "Manta–Portoviejo E691",
        "wkt": "LINESTRING(-80.7120 -0.9480, -80.5700 -1.0000, -80.4530 -1.0546)",
        "population_impact": 310_000,
        "osm_id": "w55678005",
        # HIGH risk — Manabí coastal, heavily affected in 2023
        "risks": {24: 0.78, 48: 0.84, 72: 0.90},
        "alert": True,
    },
    {
        "name": "Esmeraldas–Ibarra E10",
        "wkt": "LINESTRING(-79.6516 0.9592, -79.4000 0.6000, -79.1000 0.3500, -78.1166 0.3513)",
        "population_impact": 195_000,
        "osm_id": "w62341006",
        # HIGH risk — Esmeraldas province
        "risks": {24: 0.71, 48: 0.79, 72: 0.85},
        "alert": True,
    },
]

# Alternative routes for high-risk corridors (pre-computed WKT)
_REROUTING = {
    "Guayaquil–Machala E25": {
        "alt_wkt": "LINESTRING(-79.8975 -2.1709, -79.7000 -2.4000, -79.6000 -2.8000, -79.8000 -3.2581)",
        "distance_km": 238.5,
        "duration_minutes": 195.0,
        "via": "Vía Naranjal–Pasaje (interior)",
    },
    "Quito–Santo Domingo E28": {
        "alt_wkt": "LINESTRING(-78.5161 -0.2149, -78.6000 -0.4000, -78.9000 -0.5000, -79.1734 -0.2520)",
        "distance_km": 172.3,
        "duration_minutes": 210.0,
        "via": "Vía Aloag–Tandapi (E35 sur)",
    },
    "Manta–Portoviejo E691": {
        "alt_wkt": "LINESTRING(-80.7120 -0.9480, -80.6500 -1.1000, -80.5000 -1.0800, -80.4530 -1.0546)",
        "distance_km": 46.8,
        "duration_minutes": 68.0,
        "via": "Vía Montecristi–Crucita",
    },
    "Esmeraldas–Ibarra E10": {
        "alt_wkt": "LINESTRING(-79.6516 0.9592, -79.2000 0.7000, -78.8000 0.5000, -78.1166 0.3513)",
        "distance_km": 312.0,
        "duration_minutes": 285.0,
        "via": "Vía Lita–La Carolina (interior serrano)",
    },
}

_MUNICIPALITIES = [
    {
        "name": "Esmeraldas",
        "wkt": "MULTIPOLYGON(((-80.3 0.5, -79.1 0.5, -79.1 1.5, -80.3 1.5, -80.3 0.5)))",
        "epi_profile": {
            "malaria_cases_per_100k": 42,
            "dengue_cases_per_100k": 31,
            "diarrhea_risk": "critical",
            "cholera_risk": "high",
            "vulnerable_population": 68_000,
            "health_facilities": 4,
            "flood_affected_villages": 23,
        },
    },
    {
        "name": "Manabí (Portoviejo)",
        "wkt": "MULTIPOLYGON(((-80.7 -1.3, -80.1 -1.3, -80.1 -0.7, -80.7 -0.7, -80.7 -1.3)))",
        "epi_profile": {
            "malaria_cases_per_100k": 18,
            "dengue_cases_per_100k": 55,
            "diarrhea_risk": "high",
            "cholera_risk": "medium",
            "vulnerable_population": 120_000,
            "health_facilities": 8,
            "flood_affected_villages": 47,
        },
    },
    {
        "name": "Guayas (Guayaquil)",
        "wkt": "MULTIPOLYGON(((-80.2 -2.5, -79.5 -2.5, -79.5 -1.8, -80.2 -1.8, -80.2 -2.5)))",
        "epi_profile": {
            "malaria_cases_per_100k": 9,
            "dengue_cases_per_100k": 28,
            "diarrhea_risk": "high",
            "cholera_risk": "low",
            "vulnerable_population": 310_000,
            "health_facilities": 22,
            "flood_affected_villages": 18,
        },
    },
    {
        "name": "El Oro (Machala)",
        "wkt": "MULTIPOLYGON(((-80.3 -3.5, -79.6 -3.5, -79.6 -2.9, -80.3 -2.9, -80.3 -3.5)))",
        "epi_profile": {
            "malaria_cases_per_100k": 12,
            "dengue_cases_per_100k": 19,
            "diarrhea_risk": "medium",
            "cholera_risk": "low",
            "vulnerable_population": 45_000,
            "health_facilities": 6,
            "flood_affected_villages": 11,
        },
    },
    {
        "name": "Pichincha (Quito)",
        "wkt": "MULTIPOLYGON(((-79.0 -0.5, -78.1 -0.5, -78.1 0.1, -79.0 0.1, -79.0 -0.5)))",
        "epi_profile": {
            "malaria_cases_per_100k": 1,
            "dengue_cases_per_100k": 4,
            "diarrhea_risk": "low",
            "cholera_risk": "low",
            "vulnerable_population": 85_000,
            "health_facilities": 35,
            "flood_affected_villages": 3,
        },
    },
    {
        "name": "Los Ríos (Babahoyo)",
        "wkt": "MULTIPOLYGON(((-80.0 -2.1, -79.3 -2.1, -79.3 -1.5, -80.0 -1.5, -80.0 -2.1)))",
        "epi_profile": {
            "malaria_cases_per_100k": 28,
            "dengue_cases_per_100k": 44,
            "diarrhea_risk": "critical",
            "cholera_risk": "high",
            "vulnerable_population": 92_000,
            "health_facilities": 5,
            "flood_affected_villages": 38,
        },
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

async def run_seed_demo() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await _seed(session)
            await session.commit()
            log.info("Demo seed complete")
        except Exception:
            await session.rollback()
            log.exception("Demo seed failed — rolled back")
            raise


async def _seed(session: AsyncSession) -> None:
    # Idempotency check — skip if demo corridors exist
    existing = await session.execute(
        select(Corridor).where(Corridor.is_demo == True).limit(1)  # noqa: E712
    )
    if existing.scalar_one_or_none():
        log.info("Demo data already present — skipping seed")
        return

    now = datetime.now(timezone.utc)

    # --- Municipalities ---
    mun_records = []
    for m in _MUNICIPALITIES:
        mun = Municipality(
            name=m["name"],
            geometry=WKTElement(m["wkt"], srid=4326),
            country="EC",
            epi_profile=m["epi_profile"],
        )
        session.add(mun)
        mun_records.append(mun)

    await session.flush()  # get IDs

    # --- Corridors + Forecasts + Alerts + Rerouting ---
    for c in _CORRIDORS:
        corridor = Corridor(
            name=c["name"],
            geometry=WKTElement(c["wkt"], srid=4326),
            population_impact=c["population_impact"],
            country="EC",
            osm_id=c["osm_id"],
            is_demo=True,
        )
        session.add(corridor)
        await session.flush()  # get UUID

        # Risk forecasts for 24 / 48 / 72 h
        for horizon, prob in c["risks"].items():
            forecast = RiskForecast(
                corridor_id=corridor.id,
                horizon_hours=horizon,
                probability=prob,
                computed_at=now,
                valid_from=now + timedelta(hours=horizon - 24),
                is_demo=True,
            )
            session.add(forecast)

        # Alert if any horizon > threshold
        max_prob = max(c["risks"].values())
        if c["alert"] and max_prob >= settings.RISK_THRESHOLD:
            alert = Alert(
                corridor_id=corridor.id,
                probability=max_prob,
                horizon_hours=24,
                generated_at=now,
                is_active=True,
                is_demo=True,
            )
            session.add(alert)

        # Rerouting plan if one is defined
        reroute = _REROUTING.get(c["name"])
        if reroute:
            plan = ReroutingPlan(
                corridor_id=corridor.id,
                geometry=WKTElement(reroute["alt_wkt"], srid=4326),
                distance_km=reroute["distance_km"],
                duration_minutes=reroute["duration_minutes"],
                via_description=reroute["via"],
                computed_at=now,
            )
            session.add(plan)

    await session.flush()
    log.info(
        "Seeded %d corridors, %d municipalities",
        len(_CORRIDORS),
        len(_MUNICIPALITIES),
    )
