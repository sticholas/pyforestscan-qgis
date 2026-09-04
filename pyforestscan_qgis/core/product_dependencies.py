"""Execution dependencies for release products."""

from __future__ import annotations

from .types import ProductType


# Every logical polygon request currently invokes its public PyForestScan path
# independently. Shared calculations are implementation opportunities, not
# durable output dependencies, so one product failure must not skip another.
PRODUCT_DEPENDENCIES: dict[ProductType, tuple[ProductType, ...]] = {
    ProductType.CHM: (),
    ProductType.DTM: (),
    ProductType.PAD: (),
    ProductType.PAI: (),
    ProductType.FHD: (),
    ProductType.CANOPY_COVER: (),
    ProductType.RUMPLE: (),
    ProductType.POINT_DENSITY: (),
    ProductType.VOXEL_STAT: (),
}


def blocked_by_failed_dependency(product: ProductType, failed: set[ProductType]) -> tuple[ProductType, ...]:
    return tuple(dependency for dependency in PRODUCT_DEPENDENCIES[product] if dependency in failed)
