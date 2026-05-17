from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RealtimeLandslideEvent(Base):
    """Near-real-time landslide event sourced from NASA LHASA-NRT."""

    __tablename__ = "realtime_landslide_events"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    geometry: Mapped[bytes] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)  # 'low' | 'moderate' | 'high'
    source: Mapped[str] = mapped_column(Text, nullable=False, default="lhasa-nrt")
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
