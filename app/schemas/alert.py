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
