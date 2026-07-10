"""QGIS-free polygon selection helpers for folder processing."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds2D:
    """Simple XY bounds."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def area(self) -> float:
        return max(0.0, self.xmax - self.xmin) * max(0.0, self.ymax - self.ymin)

    def intersects(self, other: "Bounds2D") -> bool:
        return not (self.xmax < other.xmin or other.xmax < self.xmin or self.ymax < other.ymin or other.ymax < self.ymin)

    def to_ept_bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return ((self.xmin, self.xmax), (self.ymin, self.ymax))


@dataclass(frozen=True)
class PolygonSelection:
    """Polygon geometry selected for folder processing."""

    wkt: str
    crs: str
    bounds: Bounds2D
    source_label: str = "polygon"


def polygon_selection_from_wkt(wkt: str, crs: str, *, source_label: str = "polygon WKT") -> PolygonSelection:
    """Validate polygon WKT enough for QGIS-free planning and derive bounds."""
    text = (wkt or "").strip()
    if not text:
        raise ValueError("Polygon WKT is required.")
    upper = text.upper()
    if "POLYGON" not in upper:
        raise ValueError("Polygon WKT must be POLYGON or MULTIPOLYGON geometry.")
    if not (crs or "").strip():
        raise ValueError("Polygon CRS is required.")
    coords = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)]
    if len(coords) < 6 or len(coords) % 2 != 0:
        raise ValueError("Polygon WKT does not contain enough XY coordinates.")
    xs = coords[0::2]
    ys = coords[1::2]
    bounds = Bounds2D(min(xs), min(ys), max(xs), max(ys))
    if bounds.area <= 0:
        raise ValueError("Polygon geometry has empty bounds.")
    return PolygonSelection(text, crs.strip(), bounds, source_label)
