import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corridor_id: uuid.UUID
    probability: float
    horizon_hours: int
    generated_at: datetime
    is_active: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AlertWithCorridorOut(BaseModel):
    """Alert enriched with corridor metadata — used by the dashboard panel."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    corridor_id: uuid.UUID
    corridor_name: str
    population_impact: int
    probability: float
    horizon_hours: int
    generated_at: datetime
    is_active: bool
    is_demo: bool
