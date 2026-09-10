"""Authoritative source-point anchors and point-to-point measurements."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import re
from time import monotonic
from uuid import uuid4


MAX_MEASUREMENTS = 500
MAX_SNAP_DISTANCE = 1.0


def source_pick_tolerance(point):
    """Allow float rendering roundoff while refusing arbitrary scene positions."""
    values = _point(point, "Measurement pick")
    return min(MAX_SNAP_DISTANCE, max(1e-6, max(1.0, *(abs(v) for v in values))*1e-8))


def _point(value, label):
    result = tuple(value)
    if (len(result) != 3 or any(type(item) not in (int, float)
                                or not math.isfinite(item) for item in result)):
        raise ValueError(f"{label} requires finite source XYZ coordinates.")
    return tuple(float(item) for item in result)


@dataclass(frozen=True)
class MeasurementAnchor:
    requested_xyz: tuple[float, float, float]
    source_xyz: tuple[float, float, float]
    snap_distance: float
    classification: int | None = None
    height_above_ground: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "requested_xyz", _point(self.requested_xyz, "Requested anchor"))
        object.__setattr__(self, "source_xyz", _point(self.source_xyz, "Resolved anchor"))
        if (type(self.snap_distance) not in (int, float) or not math.isfinite(self.snap_distance)
                or self.snap_distance < 0 or self.snap_distance > MAX_SNAP_DISTANCE):
            raise ValueError("Measurement anchor snap distance is invalid.")
        if self.classification is not None and (type(self.classification) is not int
                                                or not 0 <= self.classification <= 255):
            raise ValueError("Measurement anchor classification is invalid.")
        if self.height_above_ground is not None and not math.isfinite(self.height_above_ground):
            raise ValueError("Measurement anchor HAG is invalid.")


@dataclass(frozen=True)
class PointMeasurement:
    measurement_id: str
    source_sha256: str
    source_crs: str
    start: MeasurementAnchor
    end: MeasurementAnchor
    horizontal_distance: float
    vertical_distance: float
    elevation_difference: float
    distance_3d: float
    horizontal_unit: str
    vertical_unit: str
    unit_warning: str = ""
    resolution_seconds: float = 0.0
    source_point_count: int = 0
    created_at: str = ""
    addressing: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_POINT_RESOLUTION"
    kind: str = "POINT_DISTANCE"

    def __post_init__(self):
        if (not self.measurement_id or not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)
                or not self.source_crs or self.addressing !=
                "FULL_RESOLUTION_ORIGINAL_SOURCE_POINT_RESOLUTION"
                or self.kind != "POINT_DISTANCE"):
            raise ValueError("Measurement source identity is invalid.")
        for value in (self.horizontal_distance, self.vertical_distance,
                      self.elevation_difference, self.distance_3d):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Measurement distances must be finite.")
        if (self.horizontal_distance < 0 or self.vertical_distance < 0
                or self.distance_3d < 0 or not self.horizontal_unit or not self.vertical_unit):
            raise ValueError("Measurement distances and units are invalid.")
        if (type(self.resolution_seconds) not in (int, float)
                or not math.isfinite(self.resolution_seconds) or self.resolution_seconds < 0
                or type(self.source_point_count) is not int or self.source_point_count <= 0):
            raise ValueError("Measurement resolution evidence is invalid.")

    def to_dict(self):
        return asdict(self)


def _ring(value):
    points = tuple(tuple(point) for point in value)
    if not 4 <= len(points) <= 2049:
        raise ValueError("Area measurement requires 3 to 2,048 boundary vertices.")
    result = []
    for point in points:
        if (len(point) != 2 or any(type(item) not in (int, float)
                                  or not math.isfinite(item) for item in point)):
            raise ValueError("Area boundary requires finite source XY coordinates.")
        result.append((float(point[0]), float(point[1])))
    if result[0] != result[-1] or len(set(result[:-1])) < 3:
        raise ValueError("Area boundary must be a closed polygon with three distinct vertices.")
    return tuple(result)


def _area_metrics(vertices):
    origin_x, origin_y = vertices[0]
    area = abs(sum((a[0]-origin_x)*(b[1]-origin_y)
                   -(b[0]-origin_x)*(a[1]-origin_y)
                   for a, b in zip(vertices, vertices[1:]))) / 2
    perimeter = sum(math.hypot(b[0]-a[0], b[1]-a[1])
                    for a, b in zip(vertices, vertices[1:]))
    return area, perimeter


@dataclass(frozen=True)
class AreaMeasurement:
    measurement_id: str
    source_sha256: str
    source_crs: str
    vertices: tuple[tuple[float, float], ...]
    area: float
    perimeter: float
    horizontal_unit: str
    area_unit: str
    display_elevation: float
    unit_warning: str = ""
    created_at: str = ""
    addressing: str = "SOURCE_COORDINATE_PLANAR_GEOMETRY"
    kind: str = "PLANAR_AREA"

    def __post_init__(self):
        if (not self.measurement_id or not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)
                or not self.source_crs or self.addressing != "SOURCE_COORDINATE_PLANAR_GEOMETRY"
                or self.kind != "PLANAR_AREA"):
            raise ValueError("Area measurement source identity is invalid.")
        vertices = _ring(self.vertices)
        object.__setattr__(self, "vertices", vertices)
        expected_area, expected_perimeter = _area_metrics(vertices)
        if (type(self.area) not in (int, float) or not math.isfinite(self.area)
                or type(self.perimeter) not in (int, float) or not math.isfinite(self.perimeter)
                or self.area <= 0 or self.perimeter <= 0
                or not math.isclose(self.area, expected_area, rel_tol=1e-12, abs_tol=1e-9)
                or not math.isclose(self.perimeter, expected_perimeter,
                                     rel_tol=1e-12, abs_tol=1e-9)):
            raise ValueError("Saved area measurement metrics do not match its boundary.")
        if (not self.horizontal_unit or not self.area_unit
                or type(self.display_elevation) not in (int, float)
                or not math.isfinite(self.display_elevation)):
            raise ValueError("Area measurement units or display elevation are invalid.")

    def to_dict(self):
        return asdict(self)


def resolve_anchor_chunks(chunks, expected_points, requested_points, *,
                          cancelled=lambda: False, progress=lambda count: None):
    """Resolve renderer-picked coordinates to original points in one bounded scan."""
    requests = tuple(_point(item, "Measurement pick") for item in requested_points)
    if not 1 <= len(requests) <= 8:
        raise ValueError("Resolve between one and eight measurement anchors at a time.")
    if type(expected_points) is not int or expected_points <= 0:
        raise ValueError("Measurement resolution requires a positive verified point count.")
    import numpy as np

    tolerances = tuple(source_pick_tolerance(item) for item in requests)
    best = [None] * len(requests)
    scanned = 0
    started = monotonic()
    for chunk in chunks:
        if cancelled():
            raise InterruptedError("Measurement cancelled; saved measurements are unchanged.")
        names = set(chunk.dtype.names or ())
        if not {"X", "Y", "Z"}.issubset(names):
            raise ValueError("Source does not contain XYZ measurement coordinates.")
        x = np.asarray(chunk["X"], dtype="f8")
        y = np.asarray(chunk["Y"], dtype="f8")
        z = np.asarray(chunk["Z"], dtype="f8")
        finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        for index, request in enumerate(requests):
            distance2 = ((x-request[0])**2 + (y-request[1])**2
                         + (z-request[2])**2)
            if not len(distance2):
                continue
            distance2 = np.where(finite, distance2, np.inf)
            location = int(np.argmin(distance2))
            candidate = float(distance2[location])
            if math.isfinite(candidate) and (best[index] is None or candidate < best[index][0]):
                classification = (int(chunk["Classification"][location])
                                  if "Classification" in names else None)
                hag = (float(chunk["HeightAboveGround"][location])
                       if "HeightAboveGround" in names else None)
                if hag is not None and not math.isfinite(hag):
                    hag = None
                best[index] = (candidate,
                    (float(x[location]), float(y[location]), float(z[location])),
                    classification, hag)
        scanned += len(chunk)
        progress(scanned)
    if scanned != expected_points:
        raise ValueError("Measurement source count differs from the verified header.")
    anchors = []
    for request, tolerance, candidate in zip(requests, tolerances, best):
        if candidate is None or math.sqrt(candidate[0]) > tolerance:
            raise ValueError("A picked location could not be matched to an original source point.")
        anchors.append(MeasurementAnchor(request, candidate[1], math.sqrt(candidate[0]),
                                         candidate[2], candidate[3]))
    return tuple(anchors), monotonic()-started


def create_point_measurement(source_sha256, source_crs, anchors, *,
                             horizontal_unit, vertical_unit=None,
                             unit_warning="", resolution_seconds=0,
                             source_point_count=1, measurement_id=None, created_at=None):
    items = tuple(anchors)
    if len(items) != 2 or any(not isinstance(item, MeasurementAnchor) for item in items):
        raise ValueError("Point-to-point measurement requires two resolved source anchors.")
    ax, ay, az = items[0].source_xyz
    bx, by, bz = items[1].source_xyz
    horizontal = math.hypot(bx-ax, by-ay)
    elevation = bz-az
    vertical = abs(elevation)
    distance = math.hypot(horizontal, elevation)
    return PointMeasurement(measurement_id or uuid4().hex, source_sha256, source_crs,
        items[0], items[1], horizontal, vertical, elevation, distance,
        horizontal_unit, vertical_unit or horizontal_unit, unit_warning,
        resolution_seconds, source_point_count,
        created_at or datetime.now(timezone.utc).isoformat())


def create_area_measurement(source_sha256, source_crs, vertices, *,
                            horizontal_unit, display_elevation, unit_warning="",
                            measurement_id=None, created_at=None, polygon_type=None):
    """Validate and calculate a horizontal area in source CRS coordinates."""
    points = _ring(vertices)
    if polygon_type is None:
        from shapely.geometry import Polygon
        polygon_type = Polygon
    polygon = polygon_type(points)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError("Area boundary is empty or invalid; redraw a simple polygon.")
    area, perimeter = _area_metrics(points)
    return AreaMeasurement(measurement_id or uuid4().hex, source_sha256, source_crs,
        points, area, perimeter, horizontal_unit, f"square {horizontal_unit}",
        display_elevation, unit_warning,
        created_at or datetime.now(timezone.utc).isoformat())


def measurement_unit_context(source_crs, crs_type):
    """Return explicit unit labels from a pyproj-like CRS type."""
    if source_crs.startswith("SOURCE_LOCAL:"):
        return "source units", "source units", "CRS units are unknown; values use source coordinates."
    crs = crs_type.from_user_input(source_crs)
    if crs.is_geographic:
        raise ValueError("Point-to-point measurement requires a projected or source-local CRS; geographic angular coordinates are not mixed with elevation.")
    axes = tuple(crs.axis_info or ())
    horizontal = axes[0].unit_name if axes and axes[0].unit_name else "projected units"
    vertical = axes[2].unit_name if len(axes) > 2 and axes[2].unit_name else horizontal
    warning = ""
    if vertical != horizontal:
        warning = "Horizontal and vertical axes use different units; 3D distance combines source coordinate values."
    return horizontal, vertical, warning


def resolve_source_measurement(source, expected_points, requested_points, source_crs, *,
                               pdal_module=None, crs_type=None,
                               cancelled=lambda: False, progress=lambda count: None):
    """Verify one source, resolve two picked anchors, and calculate its distances."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    if crs_type is None:
        from pyproj import CRS
        crs_type = CRS
    source.verify(cancelled=cancelled)
    reader = {"type":"readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename":source.path}
    chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=65_536, prefetch=0)
    anchors, duration = resolve_anchor_chunks(chunks, expected_points, requested_points,
                                              cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    horizontal, vertical, warning = measurement_unit_context(source_crs, crs_type)
    return create_point_measurement(source.sha256, source_crs, anchors,
        horizontal_unit=horizontal, vertical_unit=vertical, unit_warning=warning,
        resolution_seconds=duration, source_point_count=expected_points)


def measurement_summary(measurement):
    item = measurement if isinstance(measurement, (PointMeasurement, AreaMeasurement)) else measurement_from_dict(measurement)
    if isinstance(item, AreaMeasurement):
        return (f"Area {item.area:,.3f} {item.area_unit} | "
                f"Perimeter {item.perimeter:,.3f} {item.horizontal_unit}")
    return (f"3D {item.distance_3d:,.3f} {item.horizontal_unit} | "
            f"Horizontal {item.horizontal_distance:,.3f} {item.horizontal_unit} | "
            f"Elevation change {item.elevation_difference:+,.3f} {item.vertical_unit}")


def measurement_from_dict(payload):
    if not isinstance(payload, dict):
        raise ValueError("Saved measurement is invalid.")
    values = dict(payload)
    try:
        if values.get("kind") == "PLANAR_AREA":
            return AreaMeasurement(**values)
        values["start"] = MeasurementAnchor(**values["start"])
        values["end"] = MeasurementAnchor(**values["end"])
        return PointMeasurement(**values)
    except (KeyError, TypeError) as error:
        raise ValueError("Saved measurement is incomplete.") from error


def validate_measurements(payload, source_sha256):
    if payload in (None, []):
        return []
    if not isinstance(payload, list) or len(payload) > MAX_MEASUREMENTS:
        raise ValueError(f"One session supports at most {MAX_MEASUREMENTS:,} measurements.")
    result = []
    ids = set()
    for raw in payload:
        item = measurement_from_dict(raw)
        if item.source_sha256 != source_sha256:
            raise ValueError("Saved measurement belongs to another source.")
        if item.measurement_id in ids:
            raise ValueError("Saved measurements contain duplicate identities.")
        ids.add(item.measurement_id)
        result.append(item.to_dict())
    return result
