"""
Risk pipeline — runs every configured interval via APScheduler.
Fetches Open-Meteo precipitation for each non-demo corridor,
scores landslide probability, stores forecasts, and triggers alerts.
"""
import logging
from datetime import datetime, timedelta, timezone

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString
from shapely.ops import substring
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories import AlertRepo, CorridorRepo, ForecastRepo, RiskSegmentRepo
from app.db.session import AsyncSessionLocal
from app.integrations.open_meteo import aggregate_precipitation, get_precipitation_forecasts
from app.models.alert import Alert
from app.models.risk_forecast import RiskForecast
from app.models.risk_segment import RiskSegment
from app.pipeline.processors.risk_scorer import compute_probabilities
from app.pipeline.processors.susceptibility import get_susceptibility

log = logging.getLogger(__name__)


async def run_risk_pipeline() -> None:
    """Entry point called by APScheduler — manages its own session."""
    log.info("Risk pipeline started")
    async with AsyncSessionLocal() as session:
        try:
            processed, alerted = await _pipeline(session)
            await session.commit()
            log.info("Risk pipeline done — %d corridors processed, %d alerts generated", processed, alerted)
        except Exception:
            await session.rollback()
            log.exception("Risk pipeline failed — rolled back")
            raise


async def _pipeline(session: AsyncSession) -> tuple[int, int]:
    corridor_repo = CorridorRepo(session)
    forecast_repo = ForecastRepo(session)
    alert_repo = AlertRepo(session)
    segment_repo = RiskSegmentRepo(session)

    corridors = await corridor_repo.list_all(is_demo=False)
    if not corridors:
        log.info("No real corridors in DB — skipping pipeline")
        return 0, 0

    now = datetime.now(timezone.utc)
    processed = 0
    alerted = 0

    for corridor in corridors:
        try:
            segment_results = await _score_corridor_segments(corridor)
            probs = _peak_probabilities(segment_results)

            for horizon, prob in probs.items():
                forecast = RiskForecast(
                    corridor_id=corridor.id,
                    horizon_hours=horizon,
                    probability=prob,
                    computed_at=now,
                    valid_from=now + timedelta(hours=horizon - 24),
                    is_demo=False,
                )
                await forecast_repo.insert(forecast)

            # Alert if any horizon breaches threshold — surface the highest-risk one
            peak_horizon = max(probs, key=probs.__getitem__)
            peak_prob = probs[peak_horizon]
            await alert_repo.deactivate_by_corridor(corridor.id, is_demo=False)
            if peak_prob >= settings.RISK_THRESHOLD:
                alert = Alert(
                    corridor_id=corridor.id,
                    probability=peak_prob,
                    horizon_hours=peak_horizon,
                    generated_at=now,
                    is_active=True,
                    is_demo=False,
                )
                await alert_repo.insert(alert)
                alerted += 1

            await segment_repo.deactivate_by_corridor(corridor.id, is_demo=False)
            for result in segment_results:
                if result["probability"] < 0.20:
                    continue
                await segment_repo.insert(
                    RiskSegment(
                        corridor_id=corridor.id,
                        geometry=WKTElement(result["geometry"].wkt, srid=4326),
                        segment_index=result["segment_index"],
                        horizon_hours=result["horizon_hours"],
                        probability=result["probability"],
                        susceptibility_class=result["susceptibility_class"],
                        computed_at=now,
                        valid_from=now + timedelta(hours=result["horizon_hours"] - 24),
                        is_active=True,
                        is_demo=False,
                    )
                )

            processed += 1

        except Exception:
            log.exception("Failed to process corridor %s (%s)", corridor.id, corridor.name)
            continue  # don't abort the whole run for one corridor

    return processed, alerted


async def _score_corridor_segments(corridor) -> list[dict]:
    line = to_shape(corridor.geometry)
    if not isinstance(line, LineString) or line.length == 0:
        return []

    count = max(settings.RISK_SEGMENT_COUNT, 1)
    segments = []
    points = []
    susceptibility = []
    for index in range(count):
        start = line.length * index / count
        end = line.length * (index + 1) / count
        segment = substring(line, start, end)
        if segment.is_empty or segment.length == 0:
            continue

        midpoint = segment.interpolate(0.5, normalized=True)
        segments.append((index, segment))
        points.append((midpoint.y, midpoint.x))
        susceptibility.append(get_susceptibility(midpoint.y, midpoint.x))

    results = await _score_segments(corridor.name, segments, points, susceptibility)

    if not results:
        centroid = line.centroid
        results = await _score_segments(
            corridor.name,
            [(0, line)],
            [(centroid.y, centroid.x)],
            [get_susceptibility(centroid.y, centroid.x)],
        )

    return results


async def _score_segments(
    corridor_name: str,
    segments: list[tuple[int, LineString]],
    points: list[tuple[float, float]],
    susceptibility: list[int],
) -> list[dict]:
    try:
        forecasts = await get_precipitation_forecasts(points)
    except Exception:
        log.exception("Failed to score segments for corridor %s", corridor_name)
        forecasts = [{} for _ in segments]

    results = []
    for (index, segment), forecast, susc_class in zip(segments, forecasts, susceptibility, strict=False):
        mm_24, mm_48, mm_72 = aggregate_precipitation(forecast)
        probs = compute_probabilities(mm_24, mm_48, mm_72, susceptibility_class=susc_class)
        for horizon, probability in probs.items():
            results.append(
                {
                    "geometry": segment,
                    "segment_index": index,
                    "horizon_hours": horizon,
                    "probability": probability,
                    "susceptibility_class": susc_class,
                }
            )
    return results


def _peak_probabilities(segment_results: list[dict]) -> dict[int, float]:
    peaks = {24: 0.02, 48: 0.02, 72: 0.02}
    for result in segment_results:
        horizon = result["horizon_hours"]
        peaks[horizon] = max(peaks[horizon], result["probability"])
    return peaks
