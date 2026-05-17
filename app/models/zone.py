import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Zone(Base, TimestampMixin):
    """Administrative zone (canton / parroquia) with PostGIS polygon."""

    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("code", "level", name="uq_zones_code_level"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # 'canton' | 'parroquia'
    country: Mapped[str] = mapped_column(Text, nullable=False, default="EC", index=True)
    geometry: Mapped[bytes] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=False
    )
