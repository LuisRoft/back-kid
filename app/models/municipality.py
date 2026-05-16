import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Municipality(Base, TimestampMixin):
    """Municipality with PostGIS geometry and PAHO epidemiological profile."""

    __tablename__ = "municipalities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    geometry: Mapped[bytes] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=False
    )
    country: Mapped[str] = mapped_column(Text, nullable=False, default="EC")
    # Historical epidemiological profile from PAHO/SIVIGILA
    # Shape: { "dengue": [...], "cholera": [...], "respiratory": [...] }
    epi_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
