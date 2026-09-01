"""QGIS-free normalized polygon geometry and exact core intersections."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .polygon_transport import wkt_to_geojson_geometry

Point = tuple[float, float]
Ring = tuple[Point, ...]
Part = tuple[Ring, ...]
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class NormalizedPolygonGeometry:
    """Immutable, validated polygon representation reused for an entire plan."""
    geometry_type: str
    parts: tuple[Part, ...]
    bounds: Bounds
    part_bounds: tuple[Bounds, ...]
    ring_bounds: tuple[tuple[Bounds, ...], ...]
    source_crs: str
    processing_crs: str
    coordinate_domain: str
    polygon_signature: str
    vertex_count: int

    @classmethod
    def from_wkt(cls, wkt: str, *, source_crs: str = "", processing_crs: str = "") -> "NormalizedPolygonGeometry":
        geometry = wkt_to_geojson_geometry(wkt, crs=processing_crs or source_crs, source_crs=source_crs)
        return cls.from_geojson(geometry, source_crs=source_crs, processing_crs=processing_crs, signature_source=wkt.strip())

    @classmethod
    def from_geojson(cls, geometry: dict[str, Any], *, source_crs: str = "", processing_crs: str = "", signature_source: str = "") -> "NormalizedPolygonGeometry":
        geometry_type = str(geometry.get("type", ""))
        raw_parts = geometry.get("coordinates", ())
        if geometry_type == "Polygon":
            raw_parts = (raw_parts,)
        elif geometry_type != "MultiPolygon":
            raise ValueError("Normalized geometry must be Polygon or MultiPolygon.")
        parts: tuple[Part, ...] = tuple(tuple(tuple((float(point[0]), float(point[1])) for point in ring) for ring in part) for part in raw_parts)
        if not parts or not any(parts):
            raise ValueError("Normalized polygon geometry is empty.")
        ring_bounds = tuple(tuple(_bounds(ring) for ring in part) for part in parts)
        part_bounds = tuple(_merge_bounds(bounds) for bounds in ring_bounds)
        bounds = _merge_bounds(part_bounds)
        signature_payload = signature_source or repr((geometry_type, parts, source_crs, processing_crs))
        coordinate_domain = "geographic" if (processing_crs or source_crs).upper() in {"EPSG:4326", "CRS:84"} else "projected_or_unknown"
        return cls(geometry_type, parts, bounds, part_bounds, ring_bounds, source_crs, processing_crs, coordinate_domain, hashlib.sha256(signature_payload.encode("utf-8")).hexdigest(), sum(len(ring) for part in parts for ring in part))


@dataclass(frozen=True)
class CorePolygonIntersection:
    intersects: bool
    intersection_area: float
    coverage_percent: float
    boundary_touch_only: bool


def normalize_polygon_geometry(polygon: str | dict[str, Any] | NormalizedPolygonGeometry, *, source_crs: str = "", processing_crs: str = "") -> NormalizedPolygonGeometry:
    if isinstance(polygon, NormalizedPolygonGeometry):
        return polygon
    if isinstance(polygon, dict):
        return NormalizedPolygonGeometry.from_geojson(polygon, source_crs=source_crs, processing_crs=processing_crs)
    return NormalizedPolygonGeometry.from_wkt(str(polygon), source_crs=source_crs, processing_crs=processing_crs)


def measure_core_polygon_intersection(extent, polygon):
    """Measure exact area, accepting WKT for compatibility or normalized geometry for hot loops."""
    normalized = normalize_polygon_geometry(polygon)
    extent_bounds = (extent.xmin, extent.ymin, extent.xmax, extent.ymax)
    core_area = max(0.0, extent.width * extent.height)
    if not _overlaps(extent_bounds, normalized.bounds):
        return CorePolygonIntersection(False, 0.0, 0.0, False)
    area = 0.0
    touch = False
    for index, part in enumerate(normalized.parts):
        if not _overlaps(extent_bounds, normalized.part_bounds[index]):
            continue
        exterior = _clipped_ring_area(part[0], extent) if part else 0.0
        holes = sum(_clipped_ring_area(ring, extent) for ring_index, ring in enumerate(part[1:], 1) if _overlaps(extent_bounds, normalized.ring_bounds[index][ring_index]))
        area += max(0.0, exterior - holes)
        touch = touch or _boundary_touches(part, extent)
    area = min(core_area, max(0.0, area))
    return CorePolygonIntersection(area > 1e-9, area, (area / core_area * 100.0) if core_area else 0.0, touch and area <= 1e-9)


def _bounds(points: Ring) -> Bounds:
    xs = tuple(point[0] for point in points); ys = tuple(point[1] for point in points)
    return min(xs), min(ys), max(xs), max(ys)


def _merge_bounds(items: tuple[Bounds, ...]) -> Bounds:
    return min(x[0] for x in items), min(x[1] for x in items), max(x[2] for x in items), max(x[3] for x in items)


def _overlaps(left: Bounds, right: Bounds) -> bool:
    return not (left[2] <= right[0] or left[0] >= right[2] or left[3] <= right[1] or left[1] >= right[3])


def _clipped_ring_area(ring, extent):
    points = list(ring)
    for axis, value, keep_greater in ((0, extent.xmin, True), (0, extent.xmax, False), (1, extent.ymin, True), (1, extent.ymax, False)):
        points = _clip(points, axis, value, keep_greater)
        if not points: return 0.0
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points))) / 2.0)


def _clip(points, axis, value, keep_greater):
    if not points: return []
    result = []
    def inside(point): return point[axis] >= value if keep_greater else point[axis] <= value
    def intersect(a, b):
        delta = b[axis] - a[axis]
        if abs(delta) < 1e-15: return a
        ratio = (value - a[axis]) / delta
        return (value, a[1] + ratio * (b[1] - a[1])) if axis == 0 else (a[0] + ratio * (b[0] - a[0]), value)
    previous = points[-1]; previous_inside = inside(previous)
    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside: result.append(intersect(previous, current))
            result.append(current)
        elif previous_inside: result.append(intersect(previous, current))
        previous, previous_inside = current, current_inside
    return result


def _boundary_touches(parts, extent):
    return any(extent.xmin <= x <= extent.xmax and extent.ymin <= y <= extent.ymax for ring in parts for x, y in ring)
