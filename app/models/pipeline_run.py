from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PipelineRun(Base):
    """Log of every pipeline task execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    task_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # "success" | "failed"
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
