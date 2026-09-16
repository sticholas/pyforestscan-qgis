"""Truthful capability states for products launched from viewer scopes."""

from ..product_registry import PRODUCT_DEFINITIONS
from ..types import ProductType

AVAILABLE = "AVAILABLE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"

SCOPED_EXECUTABLE_PRODUCTS = frozenset({
    ProductType.CHM, ProductType.CANOPY_COVER, ProductType.PAD,
    ProductType.PAI, ProductType.FHD, ProductType.RUMPLE,
    ProductType.DTM, ProductType.POINT_DENSITY, ProductType.VOXEL_STAT,
})

def product_scope_status(product, scope_kind):
    """Return the UI status for one product and selection kind."""
    product = ProductType(product)
    if product not in SCOPED_EXECUTABLE_PRODUCTS:
        return NOT_YET_AVAILABLE
    if scope_kind == "PROFILE" and product is not ProductType.POINT_DENSITY:
        return REVIEW_REQUIRED
    return AVAILABLE

def registered_scope_products():
    """Return all product definitions, including explicit unavailable entries."""
    return tuple(definition.product for definition in PRODUCT_DEFINITIONS)
