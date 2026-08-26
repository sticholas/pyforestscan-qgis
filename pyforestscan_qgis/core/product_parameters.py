"""Central scientific parameter defaults and PyForestScan mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductParameter:
    product: str
    name: str
    value_type: str
    default: Any
    units: str
    description: str
    advanced: bool
    function: str
    argument: str


PRODUCT_PARAMETERS = (
    ProductParameter("chm", "resolution", "float", 1.0, "map units", "Output cell size.", False, "calculate_chm", "resolution"),
    ProductParameter("rumple", "resolution", "float", 1.0, "map units", "Supporting CHM cell size.", False, "calculate_chm", "resolution"),
    ProductParameter("rumple", "min_height", "optional float", None, "height units", "Minimum canopy height included.", True, "calculate_rumple", "min_height"),
    ProductParameter("pad", "voxel_height", "float", 1.0, "height units", "Vertical voxel bin size.", False, "assign_voxels", "voxel_resolution"),
    ProductParameter("pai", "voxel_height", "float", 1.0, "height units", "Vertical voxel bin size.", False, "assign_voxels", "voxel_resolution"),
    ProductParameter("fhd", "voxel_height", "float", 1.0, "height units", "Vertical voxel bin size.", False, "assign_voxels", "voxel_resolution"),
    ProductParameter("canopy_cover", "height_threshold", "float", 2.0, "height units", "Canopy return threshold.", False, "calculate_canopy_cover", "height_cutoff"),
    ProductParameter("dtm", "resolution", "float", 1.0, "map units", "Terrain cell size.", False, "generate_dtm", "resolution"),
    ProductParameter("point_density", "resolution", "float", 1.0, "map units", "Density cell size.", False, "calculate_point_density", "voxel_resolution"),
    ProductParameter("voxel_stat", "stat", "choice", "count", "", "Voxel aggregation statistic.", True, "calculate_voxel_stat", "stat"),
)


def parameters_for_product(product: str) -> tuple[ProductParameter, ...]:
    return tuple(item for item in PRODUCT_PARAMETERS if item.product == product)
