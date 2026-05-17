import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RiskForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corridor_id: uuid.UUID
    horizon_hours: int
    probability: float
    computed_at: datetime
    valid_from: datetime
    is_demo: bool
