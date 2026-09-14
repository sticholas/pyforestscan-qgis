"""Grid, halo, aggregation, and validation primitives for adaptive Rumple."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math

from .source_aware_processing import AlignedRasterGrid, SpatialExtent


@dataclass(frozen=True)
class RumpleHaloRequirement:
    chm_cells: int = 1
    reason: str = "Each Rumple value uses one 2x2 CHM patch, so a core edge needs one neighboring CHM cell."


@dataclass(frozen=True)
class RumpleGrid:
    crs: str
    resolution: float
    transform: tuple[float, float, float, float, float, float]
    extent: SpatialExtent
    rows: int
    columns: int
    nodata: float
    chm_grid_signature: str

    @property
    def grid_signature(self) -> str:
        payload = {"crs": self.crs, "resolution": self.resolution, "transform": self.transform, "extent": self.extent.__dict__, "rows": self.rows, "columns": self.columns, "nodata": self.nodata, "chm": self.chm_grid_signature}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class RumpleTotals:
    surface_area_sum: float = 0.0
    planar_area_sum: float = 0.0
    valid_patch_count: int = 0

    @property
    def rumple_index(self) -> float:
        return self.surface_area_sum / self.planar_area_sum if self.planar_area_sum else math.nan

    def combine(self, other: "RumpleTotals") -> "RumpleTotals":
        return RumpleTotals(self.surface_area_sum + other.surface_area_sum, self.planar_area_sum + other.planar_area_sum, self.valid_patch_count + other.valid_patch_count)


def derive_rumple_grid(chm_grid: AlignedRasterGrid) -> RumpleGrid:
    if chm_grid.rows < 2 or chm_grid.columns < 2:
        raise ValueError("Rumple requires a CHM grid of at least 2 rows by 2 columns.")
    half = chm_grid.resolution / 2.0
    extent = SpatialExtent(chm_grid.total_extent.xmin + half, chm_grid.total_extent.ymin + half, chm_grid.total_extent.xmax - half, chm_grid.total_extent.ymax - half)
    transform = (extent.xmin, chm_grid.resolution, 0.0, extent.ymax, 0.0, -chm_grid.resolution)
    return RumpleGrid(chm_grid.crs, chm_grid.resolution, transform, extent, chm_grid.rows - 1, chm_grid.columns - 1, chm_grid.nodata, chm_grid.grid_signature)


def rumple_core_extent(chm_core: SpatialExtent, grid: RumpleGrid) -> SpatialExtent | None:
    half = grid.resolution / 2.0
    # Each patch is owned by the CHM core containing its lower-left grid cell.
    # Adjacent cores therefore meet at core boundary + half a cell without overlap.
    candidate = SpatialExtent(chm_core.xmin + half, chm_core.ymin + half, chm_core.xmax + half, chm_core.ymax + half)
    clipped = SpatialExtent(max(candidate.xmin, grid.extent.xmin), max(candidate.ymin, grid.extent.ymin), min(candidate.xmax, grid.extent.xmax), min(candidate.ymax, grid.extent.ymax))
    return clipped if clipped.width > 0 and clipped.height > 0 else None


def totals_from_values(values, resolution: float, *, nodata: float = -9999.0) -> RumpleTotals:
    import numpy as np
    array = np.asarray(values, dtype=float)
    valid = np.isfinite(array) & (array != nodata)
    count = int(valid.sum())
    planar = float(resolution) ** 2
    return RumpleTotals(float(array[valid].sum()) * planar, count * planar, count)


__all__ = ["RumpleGrid", "RumpleHaloRequirement", "RumpleTotals", "derive_rumple_grid", "rumple_core_extent", "totals_from_values"]
