"""Authoritative selection scopes prepared for product processing."""
from __future__ import annotations
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping

from ..product_registry import MISSION_CONTROL_PRODUCTS
from ..types import ProductType

_SCOPE_KINDS = {"AREA", "COLUMN", "PROFILE"}
_AXES = {"Z", "HeightAboveGround"}

def _range(value, label):
    if value is None:
        return None
    result = tuple(float(item) for item in value)
    if len(result) != 2 or any(not math.isfinite(item) for item in result) or result[0] > result[1]:
        raise ValueError(f"{label} must be a finite ascending range.")
    return result

@dataclass(frozen=True)
class SelectionProcessingScope:
    """Immutable source-space scope offered to a product-processing launcher."""
    selection_id: str
    source_path: Path
    source_fingerprint: str
    geometry: tuple[tuple[float, float], ...]
    geometry_crs: str
    scope_kind: str
    view_title: str = ""
    point_count: int | None = None
    z_range: tuple[float, float] | None = None
    hag_range: tuple[float, float] | None = None
    vertical_axis: str = "Z"

    def __post_init__(self):
        if not self.selection_id.strip():
            raise ValueError("A selection identity is required.")
        if not self.source_path:
            raise ValueError("A source path is required.")
        if len(self.source_fingerprint) != 64 or any(c not in "0123456789abcdef" for c in self.source_fingerprint.lower()):
            raise ValueError("Selection scope requires a source fingerprint.")
        if self.scope_kind not in _SCOPE_KINDS:
            raise ValueError("Unsupported selection scope kind.")
        if not self.geometry_crs.strip():
            raise ValueError("Selection scope requires a geometry CRS.")
        ring = tuple(tuple(point) for point in self.geometry)
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise ValueError("Selection scope geometry must be a closed polygon.")
        if any(len(point) != 2 or any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in point) for point in ring):
            raise ValueError("Selection scope geometry must contain finite XY values.")
        if self.point_count is not None and (isinstance(self.point_count, bool) or not isinstance(self.point_count, int) or self.point_count < 0):
            raise ValueError("Selection scope point count must be a non-negative integer.")
        if self.vertical_axis not in _AXES:
            raise ValueError("Selection scope vertical axis must be Z or HeightAboveGround.")
        object.__setattr__(self, "geometry", ring)
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(self, "source_fingerprint", self.source_fingerprint.lower())
        object.__setattr__(self, "z_range", _range(self.z_range, "Elevation range"))
        object.__setattr__(self, "hag_range", _range(self.hag_range, "HAG range"))

    @property
    def bounds(self):
        xs = [point[0] for point in self.geometry]
        ys = [point[1] for point in self.geometry]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def height_range(self):
        return self.hag_range if self.vertical_axis == "HeightAboveGround" else self.z_range

    @property
    def summary(self):
        kind = {"AREA": "Area", "COLUMN": "Column", "PROFILE": "Profile"}[self.scope_kind]
        count = f"{self.point_count:,} source points" if self.point_count is not None else "authoritative source selection"
        height = self.height_range
        if height is None:
            return f"{kind} | {count} | all heights"
        axis = "HAG" if self.vertical_axis == "HeightAboveGround" else "elevation"
        return f"{kind} | {count} | {axis} {height[0]:g}-{height[1]:g}"

    def to_processing_context(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "source_path": str(self.source_path),
            "source_fingerprint": self.source_fingerprint,
            "geometry": [list(point) for point in self.geometry],
            "geometry_crs": self.geometry_crs,
            "scope_kind": self.scope_kind,
            "view_title": self.view_title,
            "point_count": self.point_count,
            "bounds": list(self.bounds),
            "z_range": list(self.z_range) if self.z_range is not None else None,
            "hag_range": list(self.hag_range) if self.hag_range is not None else None,
            "vertical_axis": self.vertical_axis,
            "authority": "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY",
            "original_unchanged": True,
        }

def selection_scope_from_definition(definition: Mapping[str, Any], *, source_path, source_fingerprint, point_count=None, view_title=""):
    return SelectionProcessingScope(
        selection_id=str(definition.get("selection_id", "")),
        source_path=Path(source_path),
        source_fingerprint=source_fingerprint,
        geometry=tuple(tuple(point) for point in definition.get("geometry", ())),
        geometry_crs=str(definition.get("geometry_crs", "")),
        scope_kind=str(definition.get("scope_kind", "AREA")),
        view_title=view_title or str(definition.get("view_name", "")),
        point_count=point_count,
        z_range=definition.get("z_filter"),
        hag_range=definition.get("hag_filter"),
        vertical_axis=str(definition.get("profile_axis", "Z")),
    )


@dataclass(frozen=True)
class SelectionProductOption:
    """Product choice shown for one authoritative selection scope."""

    product: ProductType
    status: str
    reason: str


def selection_product_options(scope: SelectionProcessingScope) -> tuple[SelectionProductOption, ...]:
    """Return truthful product choices without hiding scope-specific caveats.

    All currently registered Mission Control products can consume a bounded
    source-space polygon once their request adapter is wired. Profile scopes
    are marked for review because a narrow corridor can be scientifically
    unsuitable for some raster products; density/voxel products remain the
    natural first choices. No option implies that execution is already wired.
    """
    options = []
    for definition in MISSION_CONTROL_PRODUCTS:
        if scope.scope_kind == "PROFILE" and definition.product not in {
                ProductType.POINT_DENSITY, ProductType.VOXEL_STAT}:
            status = "REVIEW"
            reason = "Profile corridor is bounded; confirm raster extent and sampling before running."
        else:
            status = "AVAILABLE"
            reason = "Uses the authoritative bounded source-space selection."
        options.append(SelectionProductOption(definition.product, status, reason))
    return tuple(options)
