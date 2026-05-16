import uuid

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Corridor(Base, TimestampMixin):
    """Road corridor in Ecuador with PostGIS geometry and population impact."""

    __tablename__ = "corridors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    geometry: Mapped[bytes] = mapped_column(
        Geometry("LINESTRING", srid=4326), nullable=False
    )
    population_impact: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="EC")
    osm_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
