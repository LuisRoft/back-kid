from app.db.repositories.alert_repo import AlertRepo
from app.db.repositories.corridor_repo import CorridorRepo
from app.db.repositories.forecast_repo import ForecastRepo
from app.db.repositories.municipality_repo import MunicipalityRepo
from app.db.repositories.pipeline_run_repo import PipelineRunRepo
from app.db.repositories.poi_repo import PoiRepo
from app.db.repositories.realtime_landslide_repo import RealtimeLandslideRepo
from app.db.repositories.realtime_rain_repo import RealtimeRainRepo
from app.db.repositories.risk_segment_repo import RiskSegmentRepo
from app.db.repositories.zone_repo import ZoneRepo
from app.db.repositories.zone_risk_repo import ZoneRiskRepo

__all__ = [
    "AlertRepo",
    "CorridorRepo",
    "ForecastRepo",
    "MunicipalityRepo",
    "PipelineRunRepo",
    "PoiRepo",
    "RealtimeLandslideRepo",
    "RealtimeRainRepo",
    "RiskSegmentRepo",
    "ZoneRepo",
    "ZoneRiskRepo",
]
