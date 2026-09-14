"""QGIS-free polygon selection helpers for folder processing."""

from __future__ import annotations

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
    """Validate polygon geometry with the shared CRS-aware transport contract."""
    text = (wkt or "").strip()
    if not text:
        raise ValueError("Polygon WKT is required.")
    upper = text.upper()
    if not (upper.startswith("POLYGON") or upper.startswith("MULTIPOLYGON")):
        raise ValueError("Polygon WKT must be POLYGON or MULTIPOLYGON geometry.")
    normalized_crs = (crs or "").strip()
    if not normalized_crs:
        raise ValueError("Polygon CRS is required.")
    from .polygon_transport import wkt_to_geojson_geometry

    geometry = wkt_to_geojson_geometry(text, crs=normalized_crs)
    coordinates: list[tuple[float, float]] = []

    def collect(value: object) -> None:
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                coordinates.append((float(value[0]), float(value[1])))
            else:
                for item in value:
                    collect(item)

    collect(geometry.get("coordinates"))
    if len(coordinates) < 4:
        raise ValueError("Polygon WKT does not contain enough XY coordinates.")
    xs = [item[0] for item in coordinates]
    ys = [item[1] for item in coordinates]
    bounds = Bounds2D(min(xs), min(ys), max(xs), max(ys))
    if bounds.area <= 0:
        raise ValueError("Polygon geometry has empty bounds.")
    return PolygonSelection(text, normalized_crs, bounds, source_label)
