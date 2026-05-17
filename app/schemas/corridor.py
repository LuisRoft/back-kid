import uuid
from datetime import datetime
from typing import Any

from geoalchemy2.shape import to_shape
from pydantic import BaseModel, ConfigDict, field_validator


class CorridorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    geometry: Any  # GeoJSON dict
    population_impact: int
    country: str
    osm_id: str | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("geometry", mode="before")
    @classmethod
    def wkb_to_geojson(cls, v: Any) -> dict:
        if isinstance(v, dict):
            return v
        return to_shape(v).__geo_interface__
