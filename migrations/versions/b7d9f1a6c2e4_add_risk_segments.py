"""add risk segments

Revision ID: b7d9f1a6c2e4
Revises: a165ae827bd5
Create Date: 2026-05-17 08:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = "b7d9f1a6c2e4"
down_revision: Union[str, Sequence[str], None] = "a165ae827bd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_segments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("corridor_id", sa.UUID(), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("susceptibility_class", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_segments_corridor_id"), "risk_segments", ["corridor_id"], unique=False)
    op.create_index(op.f("ix_risk_segments_is_active"), "risk_segments", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_risk_segments_is_active"), table_name="risk_segments")
    op.drop_index(op.f("ix_risk_segments_corridor_id"), table_name="risk_segments")
    op.drop_table("risk_segments")
