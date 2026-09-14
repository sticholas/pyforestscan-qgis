"""Authoritative scientific product dependency graph."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import ProductType


class TileMode(str, Enum):
    NATIVE = "tile_native"
    BUFFERED = "tile_with_buffer"
    REDUCTION = "tile_with_global_reduction"
    GLOBAL = "global_only"


@dataclass(frozen=True)
class ProductDependencySpec:
    product: ProductType
    label: str
    direct_dependencies: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ("X", "Y", "Z")
    tile_mode: TileMode = TileMode.BUFFERED
    buffer_cells: int = 1
    finalization: str = "raster_mosaic_mask_validate_publish"
    validation: str = "raster_grid_crs_nodata_finite"


PRODUCT_DEPENDENCY_REGISTRY = {
    ProductType.CHM: ProductDependencySpec(ProductType.CHM, "Canopy Height Model", ("HAG",), buffer_cells=1),
    ProductType.DTM: ProductDependencySpec(ProductType.DTM, "Digital Terrain Model", (), buffer_cells=2),
    ProductType.PAD: ProductDependencySpec(ProductType.PAD, "Plant Area Density", ("HAG",)),
    ProductType.PAI: ProductDependencySpec(ProductType.PAI, "Plant Area Index", ("HAG",)),
    ProductType.FHD: ProductDependencySpec(ProductType.FHD, "Foliage Height Diversity", ("HAG",)),
    ProductType.CANOPY_COVER: ProductDependencySpec(ProductType.CANOPY_COVER, "Canopy Cover", ("HAG",)),
    ProductType.RUMPLE: ProductDependencySpec(ProductType.RUMPLE, "Rumple Index", ("CHM",), buffer_cells=1),
    ProductType.POINT_DENSITY: ProductDependencySpec(ProductType.POINT_DENSITY, "Point Density", (), tile_mode=TileMode.NATIVE, buffer_cells=0),
    ProductType.VOXEL_STAT: ProductDependencySpec(ProductType.VOXEL_STAT, "Voxel Statistic", ("HAG",)),
}

# Compatibility export used by existing callers; preparation nodes are resolved
# separately so product execution still remains independently checkpointable.
PRODUCT_DEPENDENCIES = {product: tuple() for product in PRODUCT_DEPENDENCY_REGISTRY}


def resolve_execution_dag(requested: tuple[ProductType, ...], *, dimensions: tuple[str, ...] = (), has_existing_hag: bool = False, has_existing_dtm: bool = False) -> tuple[str, ...]:
    """Return the minimal ordered preparation/product node list."""
    selected = tuple(dict.fromkeys(requested))
    nodes: list[str] = []
    needs_hag = any("HAG" in PRODUCT_DEPENDENCY_REGISTRY[item].direct_dependencies for item in selected)
    if needs_hag and not has_existing_hag:
        nodes.append("HAG" if (has_existing_dtm or "Classification" in dimensions) else "DTM")
        nodes.append("HAG") if nodes[-1] != "HAG" else None
    if ProductType.RUMPLE in selected and ProductType.CHM not in selected:
        nodes.append("CHM")
    nodes.extend(product.value.upper() for product in selected)
    return tuple(dict.fromkeys(nodes))


def blocked_by_failed_dependency(product: ProductType, failed: set[ProductType]) -> tuple[ProductType, ...]:
    return tuple(dependency for dependency in PRODUCT_DEPENDENCIES.get(product, ()) if dependency in failed)
