"""add risk segments active lookup index

Revision ID: c4e2a81f9b12
Revises: b7d9f1a6c2e4
Create Date: 2026-05-17 08:50:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4e2a81f9b12"
down_revision: Union[str, Sequence[str], None] = "b7d9f1a6c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_risk_segments_corridor_demo_active",
        "risk_segments",
        ["corridor_id", "is_demo", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risk_segments_corridor_demo_active", table_name="risk_segments")
