import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Identity, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RiskForecast(Base, TimestampMixin):
    """
    Risk prediction per corridor per forecast horizon.
    High-volume table — bigint identity PK to avoid UUID fragmentation.
    """

    __tablename__ = "risk_forecasts"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    corridor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,  # FK-side index — always needed per Supabase best practices
    )
    horizon_hours: Mapped[int] = mapped_column(
        Integer, nullable=False  # 24, 48 or 72
    )
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
