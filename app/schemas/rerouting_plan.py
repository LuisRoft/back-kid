import uuid
from datetime import datetime
from typing import Any

from geoalchemy2.shape import to_shape
from pydantic import BaseModel, ConfigDict, field_validator


class ReroutingPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corridor_id: uuid.UUID
    geometry: Any  # GeoJSON dict
    distance_km: float
    duration_minutes: float
    via_description: str | None
    computed_at: datetime

    @field_validator("geometry", mode="before")
    @classmethod
    def wkb_to_geojson(cls, v: Any) -> dict:
        if isinstance(v, dict):
            return v
        return to_shape(v).__geo_interface__
