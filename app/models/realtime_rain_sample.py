from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, Identity, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RealtimeRainSample(Base):
    """Snapshot of current precipitation at a grid point."""

    __tablename__ = "realtime_rain_samples"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    geometry: Mapped[bytes] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    precipitation_mm_h: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
