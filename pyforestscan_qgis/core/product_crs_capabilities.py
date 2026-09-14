"""Product-specific CRS requirements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductCrsCapability:
    product: str
    source_local_allowed: bool
    named_crs_required: bool
    reason: str


PRODUCT_CRS_CAPABILITIES = {
    "chm": ProductCrsCapability("chm", True, False, "Grid science can use source XY and HeightAboveGround."),
    "rumple": ProductCrsCapability("rumple", True, False, "Rumple derives from a source-local CHM."),
    "canopy_cover": ProductCrsCapability("canopy_cover", True, False, "Single-source gridding can retain source coordinates."),
    "pad": ProductCrsCapability("pad", True, False, "Voxel science can retain source coordinates."),
    "pai": ProductCrsCapability("pai", True, False, "Single-source integration can retain source coordinates."),
    "fhd": ProductCrsCapability("fhd", True, False, "Height-distribution science can retain source coordinates."),
    "point_density": ProductCrsCapability("point_density", True, False, "Density can be measured in known source linear units."),
    "voxel_stat": ProductCrsCapability("voxel_stat", True, False, "Voxel statistics can retain source coordinates."),
    "dtm": ProductCrsCapability("dtm", True, False, "Standalone terrain gridding can retain source coordinates."),
    "polygon_alignment": ProductCrsCapability("polygon_alignment", False, True, "Spatial comparison requires compatible real coordinate systems."),
    "reprojection": ProductCrsCapability("reprojection", False, True, "Coordinate transformation requires known source and target CRS."),
}


def product_crs_capability(product: str) -> ProductCrsCapability:
    return PRODUCT_CRS_CAPABILITIES.get(product, ProductCrsCapability(product, False, True, "This operation has not been validated for source-local execution."))


__all__ = ["PRODUCT_CRS_CAPABILITIES", "ProductCrsCapability", "product_crs_capability"]
