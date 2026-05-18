"""zone risk breakdown — add expected_rainfall_mm and peak_susceptibility_class

Revision ID: f3d8e1a47b29
Revises: e9c4a2f1b8d3
Create Date: 2026-05-17 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3d8e1a47b29"
down_revision: Union[str, Sequence[str], None] = "e9c4a2f1b8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Why the zone has the score: 24h-window rainfall that drove the peak prob
    # in the zone, and the worst LHASA susceptibility class among sampled points.
    op.add_column(
        "zone_risk_forecasts",
        sa.Column("expected_rainfall_mm", sa.Float(), nullable=True),
    )
    op.add_column(
        "zone_risk_forecasts",
        sa.Column("peak_susceptibility_class", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("zone_risk_forecasts", "peak_susceptibility_class")
    op.drop_column("zone_risk_forecasts", "expected_rainfall_mm")
