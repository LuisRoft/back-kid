import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Poi(Base, TimestampMixin):
    """Point of interest sourced from OSM Overpass.

    Types in MVP: 'hospital' | 'clinic' | 'pharmacy' | 'supermarket'.
    Albergues and humanitarian aid are NOT stored here — the agent resolves
    those on-demand via Tavily web search.
    """

    __tablename__ = "pois"
    __table_args__ = (UniqueConstraint("osm_id", "type", name="uq_pois_osm_id_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    osm_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="osm")
    geometry: Mapped[bytes] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
