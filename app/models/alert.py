import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Identity, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Alert(Base, TimestampMixin):
    """
    Generated when risk_forecast.probability > RISK_THRESHOLD.
    High-volume table — bigint identity PK.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    corridor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
