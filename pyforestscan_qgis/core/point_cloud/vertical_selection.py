"""QGIS-free vertical selection semantics for precise point-cloud interaction."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class VerticalAxis(str, Enum):
    ELEVATION = "Z"
    HEIGHT_ABOVE_GROUND = "HeightAboveGround"


@dataclass(frozen=True)
class HeightRange:
    minimum: float
    maximum: float
    axis: VerticalAxis = VerticalAxis.ELEVATION

    def __post_init__(self):
        low, high = float(self.minimum), float(self.maximum)
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError("Vertical selection range must be finite and ascending.")
        object.__setattr__(self, "minimum", low)
        object.__setattr__(self, "maximum", high)
        object.__setattr__(self, "axis", VerticalAxis(self.axis))

    @property
    def width(self) -> float:
        return self.maximum - self.minimum

    @property
    def unit_label(self) -> str:
        return "height above ground" if self.axis is VerticalAxis.HEIGHT_ABOVE_GROUND else "elevation Z"

    def contains(self, value: float) -> bool:
        return self.minimum <= float(value) <= self.maximum

    def one_unit_band(self) -> "HeightRange":
        return HeightRange(self.minimum, self.minimum + 1.0, self.axis)

    def summary(self) -> str:
        return f"{self.unit_label}: {self.minimum:g} to {self.maximum:g} source units"


@dataclass(frozen=True)
class VerticalSelectionContext:
    """The vertical meaning applied to one shape in one linked view."""
    view_id: str
    range: HeightRange | None = None
    slice_thickness: float | None = None
    depth_basis: str = "view-local"

    def __post_init__(self):
        if not str(self.view_id).strip():
            raise ValueError("A vertical selection context requires a view identity.")
        if self.slice_thickness is not None and (
            not math.isfinite(float(self.slice_thickness)) or float(self.slice_thickness) <= 0
        ):
            raise ValueError("Slice thickness must be finite and positive.")
        if not str(self.depth_basis).strip():
            raise ValueError("A depth basis is required.")

    @property
    def summary(self) -> str:
        parts = [f"View: {self.view_id}"]
        if self.range:
            parts.append(self.range.summary())
        else:
            parts.append("all vertical values")
        if self.slice_thickness is not None:
            parts.append(f"slice depth: {float(self.slice_thickness):g} XY units")
        return " | ".join(parts)
