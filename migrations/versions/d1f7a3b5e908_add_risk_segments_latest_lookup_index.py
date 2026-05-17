"""add risk segments latest lookup index

Revision ID: d1f7a3b5e908
Revises: c4e2a81f9b12
Create Date: 2026-05-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1f7a3b5e908"
down_revision: Union[str, Sequence[str], None] = "c4e2a81f9b12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_risk_segments_demo_computed_at",
        "risk_segments",
        ["is_demo", "computed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risk_segments_demo_computed_at", table_name="risk_segments")
