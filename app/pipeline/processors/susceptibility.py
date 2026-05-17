"""
LHASA susceptibility raster loader.
Clips the global GeoTIFF to Ecuador on startup and keeps it in memory
for fast per-point lookups during pipeline runs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

log = logging.getLogger(__name__)

SUSCEPTIBILITY_PATH = Path("data/susceptibility_global.tif")


@dataclass
class SusceptibilityRaster:
    data: np.ndarray
    transform: rasterio.transform.Affine
    nodata: int

    def sample(self, lat: float, lon: float) -> int:
        """Return LHASA susceptibility class (0–5) at the given point."""
        row, col = rasterio.transform.rowcol(self.transform, lon, lat)
        h, w = self.data.shape
        if not (0 <= row < h and 0 <= col < w):
            log.warning("Point (%.4f, %.4f) outside Ecuador raster bounds", lat, lon)
            return 0
        val = int(self.data[row, col])
        return 0 if val == self.nodata else val


def load_ecuador_raster() -> SusceptibilityRaster:
    """
    Clip global GeoTIFF to Ecuador bbox and return a lightweight wrapper.
    Called once at startup — takes ~0.2 s, uses ~4 MB RAM.
    """
    from app.config import settings

    if not SUSCEPTIBILITY_PATH.exists():
        raise FileNotFoundError(
            f"LHASA susceptibility raster not found at {SUSCEPTIBILITY_PATH}. "
            "Download from gpm.nasa.gov/landslides/resources.html and place in data/."
        )

    ecuador_bbox = settings.ecuador_bbox
    with rasterio.open(SUSCEPTIBILITY_PATH) as src:
        window = from_bounds(*ecuador_bbox, src.transform)
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        if src.nodata is not None:
            nodata = int(src.nodata)
        else:
            nodata = 255
            log.warning("Susceptibility raster has no nodata tag — defaulting to 255")

    log.info(
        "Susceptibility raster loaded — Ecuador crop %dx%d px, classes 0–5",
        data.shape[1],
        data.shape[0],
    )
    return SusceptibilityRaster(data=data, transform=transform, nodata=nodata)


# Module-level singleton — populated by load_ecuador_raster() at startup
_raster: SusceptibilityRaster | None = None


def init(raster: SusceptibilityRaster) -> None:
    global _raster
    _raster = raster


def get_susceptibility(lat: float, lon: float) -> int:
    """Public interface for pipeline tasks. Returns class 3 (moderate) if raster unavailable."""
    if _raster is None:
        return 3
    return _raster.sample(lat, lon)
