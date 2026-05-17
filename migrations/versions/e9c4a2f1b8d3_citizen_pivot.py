"""citizen pivot — drop rerouting_plans, add zones, zone_risk_forecasts, realtime_rain_samples, realtime_landslide_events, pois

Revision ID: e9c4a2f1b8d3
Revises: d1f7a3b5e908
Create Date: 2026-05-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


revision: str = "e9c4a2f1b8d3"
down_revision: Union[str, Sequence[str], None] = "d1f7a3b5e908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- drop rerouting_plans (removed in citizen pivot) ---
    op.drop_index(op.f("ix_rerouting_plans_corridor_id"), table_name="rerouting_plans")
    op.drop_table("rerouting_plans")

    # --- zones (admin polygons: canton / parroquia) ---
    op.create_table(
        "zones",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),  # 'canton' | 'parroquia'
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "level", name="uq_zones_code_level"),
    )
    op.create_index("ix_zones_level", "zones", ["level"], unique=False)
    op.create_index("ix_zones_country", "zones", ["country"], unique=False)

    # --- zone_risk_forecasts ---
    op.create_table(
        "zone_risk_forecasts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("zone_id", sa.UUID(), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_zone_risk_zone_id", "zone_risk_forecasts", ["zone_id"], unique=False)
    op.create_index(
        "ix_zone_risk_active_lookup",
        "zone_risk_forecasts",
        ["zone_id", "is_active", "horizon_hours"],
        unique=False,
    )

    # --- realtime_rain_samples ---
    op.create_table(
        "realtime_rain_samples",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("precipitation_mm_h", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_realtime_rain_observed_at",
        "realtime_rain_samples",
        [sa.text("observed_at DESC")],
        unique=False,
    )

    # --- realtime_landslide_events ---
    op.create_table(
        "realtime_landslide_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),  # 'low' | 'moderate' | 'high'
        sa.Column("source", sa.Text(), nullable=False),  # 'lhasa-nrt'
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_realtime_landslide_reported_at",
        "realtime_landslide_events",
        [sa.text("reported_at DESC")],
        unique=False,
    )

    # --- pois (OSM Overpass: hospital, clinic, pharmacy, supermarket) ---
    op.create_table(
        "pois",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("osm_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),  # 'hospital' | 'clinic' | 'pharmacy' | 'supermarket'
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'osm'")),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("osm_id", "type", name="uq_pois_osm_id_type"),
    )
    op.create_index("ix_pois_type", "pois", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pois_type", table_name="pois")
    op.drop_table("pois")

    op.drop_index("ix_realtime_landslide_reported_at", table_name="realtime_landslide_events")
    op.drop_table("realtime_landslide_events")

    op.drop_index("ix_realtime_rain_observed_at", table_name="realtime_rain_samples")
    op.drop_table("realtime_rain_samples")

    op.drop_index("ix_zone_risk_active_lookup", table_name="zone_risk_forecasts")
    op.drop_index("ix_zone_risk_zone_id", table_name="zone_risk_forecasts")
    op.drop_table("zone_risk_forecasts")

    op.drop_index("ix_zones_country", table_name="zones")
    op.drop_index("ix_zones_level", table_name="zones")
    op.drop_table("zones")

    # restore rerouting_plans
    op.create_table(
        "rerouting_plans",
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
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("duration_minutes", sa.Float(), nullable=False),
        sa.Column("via_description", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rerouting_plans_corridor_id"), "rerouting_plans", ["corridor_id"], unique=True)
