"""Release-pinned scientific product contract for PyForestScan QGIS.

The registry is static at runtime. It reflects the calculate API supported by
the managed backend release and never scrapes documentation or imports the
scientific stack to construct UI controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import ProductType


@dataclass(frozen=True)
class ProductParameter:
    key: str
    display_name: str
    default: Any
    minimum: float | None = None
    automatic_allowed: bool = False
    advanced: bool = True


@dataclass(frozen=True)
class ProductDefinition:
    product: ProductType
    display_name: str
    short_name: str
    description: str
    calculate_function: str
    classification: str
    dependencies: tuple[ProductType, ...]
    output_filename: str
    output_kind: str
    units: str
    parameters: tuple[ProductParameter, ...] = ()
    minimum_pyforestscan_version: str = "release-managed"


_VOXEL_HEIGHT = ProductParameter("voxel_height", "Vertical bin height", 1.0, minimum=0.001)
_MAX_HEIGHT = ProductParameter("max_height", "Maximum height", None, minimum=0.0, automatic_allowed=True)

PRODUCT_DEFINITIONS: tuple[ProductDefinition, ...] = (
    ProductDefinition(ProductType.CHM, "Canopy Height Model (CHM)", "CHM", "Maximum canopy height above ground for each output cell.", "calculate_chm", "product", (), "chm.tif", "2D GeoTIFF", "source height units", (
        ProductParameter("grid_resolution", "Horizontal resolution", 1.0, minimum=0.01),
        ProductParameter("interpolation", "Interpolation", "linear"),
    )),
    ProductDefinition(ProductType.DTM, "Digital Terrain Model (DTM)", "DTM", "Represents estimated ground elevation.", "generate_dtm", "product", (), "dtm.tif", "2D GeoTIFF", "source elevation units", (
        ProductParameter("resolution", "Horizontal resolution", 2.0, minimum=0.01),
    )),
    ProductDefinition(ProductType.PAD, "Plant Area Density (PAD)", "PAD", "Estimates plant area density by vertical layer.", "calculate_pad", "product", (), "pad.tif", "Multi-band GeoTIFF", "area per volume", (
        _VOXEL_HEIGHT,
        ProductParameter("beer_lambert_constant", "Beer-Lambert coefficient", 1.0, minimum=0.0),
        ProductParameter("drop_ground", "Exclude ground layer", True),
    )),
    ProductDefinition(ProductType.PAI, "Plant Area Index (PAI)", "PAI", "Integrates plant area density across a selected height range.", "calculate_pai", "product", (ProductType.PAD,), "pai.tif", "2D GeoTIFF", "area per area", (
        _VOXEL_HEIGHT, ProductParameter("min_height", "Minimum integration height", 1.0, minimum=0.0), _MAX_HEIGHT,
    )),
    ProductDefinition(ProductType.FHD, "Foliage Height Diversity (FHD)", "FHD", "Describes vertical diversity of LiDAR returns through the canopy.", "calculate_fhd", "product", (), "fhd.tif", "2D GeoTIFF", "unitless entropy", (
        _VOXEL_HEIGHT, ProductParameter("min_height", "Minimum canopy height", 0.0, minimum=0.0), _MAX_HEIGHT,
    )),
    ProductDefinition(ProductType.CANOPY_COVER, "Canopy Cover", "Canopy Cover", "Estimates canopy cover above a selected height threshold.", "calculate_canopy_cover", "product", (ProductType.PAD,), "canopy_cover.tif", "2D GeoTIFF", "fraction 0-1", (
        _VOXEL_HEIGHT, ProductParameter("min_height", "Minimum height", 2.0, minimum=0.0), _MAX_HEIGHT,
        ProductParameter("k", "Extinction coefficient", 0.5, minimum=0.0),
    )),
    ProductDefinition(ProductType.RUMPLE, "Rumple Index", "Rumple", "Measures canopy surface complexity relative to horizontal ground area.", "calculate_rumple", "product", (ProductType.CHM,), "rumple.tif", "2D GeoTIFF plus summary", "ratio", (
        ProductParameter("min_height", "Minimum canopy height", None, minimum=0.0, automatic_allowed=True),
    )),
    ProductDefinition(ProductType.POINT_DENSITY, "Point Density", "Point Density", "Summarizes LiDAR return density for each output cell.", "calculate_point_density", "product", (), "point_density.tif", "2D GeoTIFF", "points per output cell area", (
        ProductParameter("per_area", "Density per unit area", True),
    )),
    ProductDefinition(ProductType.VOXEL_STAT, "Voxel Statistic", "Voxel Statistic", "Computes a selected statistic for a point attribute in a 3D voxel grid.", "calculate_voxel_stat", "advanced_operation", (), "voxel_statistic.tif", "GeoTIFF", "depends on statistic"),
)

PRODUCT_BY_TYPE = {definition.product: definition for definition in PRODUCT_DEFINITIONS}
MISSION_CONTROL_PRODUCTS = tuple(definition for definition in PRODUCT_DEFINITIONS if definition.classification == "product")

CALCULATE_FUNCTION_CLASSIFICATIONS = {
    "assign_voxels": "internal_primitive",
    "calculate_canopy_cover": "product",
    "calculate_chm": "product",
    "calculate_fhd": "product",
    "calculate_pad": "product",
    "calculate_pai": "product",
    "calculate_point_density": "product",
    "calculate_rumple": "product",
    "calculate_voxel_stat": "advanced_operation",
    "generate_dtm": "product",
}


def product_definition(product: ProductType) -> ProductDefinition:
    return PRODUCT_BY_TYPE[product]
