"""
Risk pipeline — runs every 6 h via APScheduler.
Fetches Open-Meteo precipitation for each non-demo corridor,
scores landslide probability, stores forecasts, and triggers alerts.
"""
import logging
from datetime import datetime, timedelta, timezone

from geoalchemy2.shape import to_shape
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories import AlertRepo, CorridorRepo, ForecastRepo
from app.db.session import AsyncSessionLocal
from app.integrations.open_meteo import aggregate_precipitation, get_precipitation_forecast
from app.models.alert import Alert
from app.models.risk_forecast import RiskForecast
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

    corridors = await corridor_repo.list_all(is_demo=False)
    if not corridors:
        log.info("No real corridors in DB — skipping pipeline")
        return 0, 0

    now = datetime.now(timezone.utc)
    processed = 0
    alerted = 0

    for corridor in corridors:
        try:
            centroid = to_shape(corridor.geometry).centroid
            susc_class = get_susceptibility(centroid.y, centroid.x)
            weather = await get_precipitation_forecast(centroid.y, centroid.x)
            mm_24, mm_48, mm_72 = aggregate_precipitation(weather)
            probs = compute_probabilities(mm_24, mm_48, mm_72, susceptibility_class=susc_class)

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
            if peak_prob >= settings.RISK_THRESHOLD:
                await alert_repo.deactivate_by_corridor(corridor.id, is_demo=False)
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

            processed += 1

        except Exception:
            log.exception("Failed to process corridor %s (%s)", corridor.id, corridor.name)
            continue  # don't abort the whole run for one corridor

    return processed, alerted
