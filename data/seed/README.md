# Seed data

This directory holds static GeoJSON datasets loaded into the database at startup
when `SEED_BASELINE_DATA=true` or `DEMO_MODE=true`.

## Administrative zones (Ecuador)

The zone seed task (`app.pipeline.tasks.seed_zones`) reads two files:

- `ecuador_cantons.geojson` — admin level canton (≈221 features)
- `ecuador_parroquias.geojson` — admin level parroquia (≈1 100 features, optional)

Each file must be a GeoJSON `FeatureCollection`. Each feature `properties` must
include at least:

| Property | Required | Notes |
|----------|----------|-------|
| `code`   | yes      | Unique code within its level. Falls back to `DPA_CANTON` / `DPA_PARROQ` (INEC). |
| `name`   | yes      | Human-readable name. Falls back to `DPA_DESCAN` / `DPA_DESPAR`. |

Suggested source: INEC Ecuador (División Política Administrativa) published
GeoJSON; alternatively GADM level 2 / level 3 for Ecuador.

Files are optional — if missing, the seed task logs a warning and skips. The
zones table is required for the `/api/v1/map/zones` endpoint and for the
`compute_zone_risk` pipeline job.
