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


@dataclass(frozen=True)
class ProfileAnchor:
    requested_display_xyz: tuple[float, float, float]
    source_xyz: tuple[float, float, float]
    display_xyz: tuple[float, float, float]
    profile_position: tuple[float, float]
    cross_track: float
    snap_distance: float
    classification: int | None = None
    height_above_ground: float | None = None

    def __post_init__(self):
        for field, label in (("requested_display_xyz", "Requested profile anchor"),
                             ("source_xyz", "Resolved profile source anchor"),
                             ("display_xyz", "Resolved profile display anchor")):
            object.__setattr__(self, field, _point(getattr(self, field), label))
        profile = tuple(self.profile_position)
        if (len(profile) != 2 or any(type(value) not in (int, float)
                                     or not math.isfinite(value) for value in profile)):
            raise ValueError("Profile anchor requires finite along-distance and height values.")
        object.__setattr__(self, "profile_position", tuple(float(value) for value in profile))
        if (type(self.cross_track) not in (int, float) or not math.isfinite(self.cross_track)
                or type(self.snap_distance) not in (int, float)
                or not math.isfinite(self.snap_distance) or self.snap_distance < 0
                or self.snap_distance > MAX_SNAP_DISTANCE):
            raise ValueError("Profile anchor resolution evidence is invalid.")
        if self.classification is not None and (type(self.classification) is not int
                                                or not 0 <= self.classification <= 255):
            raise ValueError("Profile anchor classification is invalid.")
        if self.height_above_ground is not None and not math.isfinite(self.height_above_ground):
            raise ValueError("Profile anchor HAG is invalid.")


@dataclass(frozen=True)
class ProfileMeasurement:
    measurement_id: str
    source_sha256: str
    source_crs: str
    view_id: str
    view_name: str
    profile_geometry: dict
    start: ProfileAnchor
    end: ProfileAnchor
    along_distance: float
    vertical_distance: float
    vertical_difference: float
    cross_section_distance: float
    horizontal_unit: str
    vertical_unit: str
    vertical_axis: str
    unit_warning: str = ""
    resolution_seconds: float = 0.0
    source_point_count: int = 0
    created_at: str = ""
    addressing: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_PROFILE_RESOLUTION"
    kind: str = "PROFILE_DISTANCE"
    purpose: str = "CROSS_SECTION"

    def __post_init__(self):
        from .workspace import SliceGeometry
        if (not self.measurement_id or not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)
                or not self.source_crs or not isinstance(self.view_id, str) or not self.view_id
                or not isinstance(self.view_name, str) or not self.view_name.strip()
                or self.addressing != "FULL_RESOLUTION_ORIGINAL_SOURCE_PROFILE_RESOLUTION"
                or self.kind != "PROFILE_DISTANCE"
                or self.purpose not in ("CROSS_SECTION", "TREE_HEIGHT")):
            raise ValueError("Profile measurement source or view identity is invalid.")
        profile = SliceGeometry(**self.profile_geometry)
        object.__setattr__(self, "profile_geometry", asdict(profile))
        if self.vertical_axis != profile.vertical_axis:
            raise ValueError("Profile measurement vertical axis does not match its slice.")
        for value in (self.along_distance, self.vertical_distance,
                      self.vertical_difference, self.cross_section_distance):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Profile measurement distances must be finite.")
        if (self.along_distance < 0 or self.vertical_distance < 0
                or self.cross_section_distance < 0 or not self.horizontal_unit
                or not self.vertical_unit or type(self.source_point_count) is not int
                or self.source_point_count <= 0 or type(self.resolution_seconds) not in (int, float)
                or not math.isfinite(self.resolution_seconds) or self.resolution_seconds < 0):
            raise ValueError("Profile measurement distances, units, or evidence are invalid.")
        along = abs(self.end.profile_position[0]-self.start.profile_position[0])
        vertical = self.end.profile_position[1]-self.start.profile_position[1]
        if (not math.isclose(self.along_distance, along, rel_tol=1e-12, abs_tol=1e-9)
                or not math.isclose(self.vertical_difference, vertical,
                                    rel_tol=1e-12, abs_tol=1e-9)
                or not math.isclose(self.vertical_distance, abs(vertical),
                                    rel_tol=1e-12, abs_tol=1e-9)
                or not math.isclose(self.cross_section_distance, math.hypot(along, vertical),
                                    rel_tol=1e-12, abs_tol=1e-9)):
            raise ValueError("Saved profile measurement metrics do not match its anchors.")
        if self.purpose == "TREE_HEIGHT" and self.vertical_distance <= 0:
            raise ValueError("Tree height requires distinct base and top heights.")

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


def resolve_profile_anchor_chunks(chunks, expected_points, requested_points,
                                  profile_geometry, *, cancelled=lambda: False,
                                  progress=lambda count: None):
    """Resolve slice-display XYZ picks against original XYZ/HAG source records."""
    from .workspace import SliceGeometry
    import numpy as np

    profile = (profile_geometry if isinstance(profile_geometry, SliceGeometry)
               else SliceGeometry(**profile_geometry))
    requests = tuple(_point(item, "Profile measurement pick") for item in requested_points)
    if len(requests) not in (1, 2):
        raise ValueError("Profile resolution requires one or two displayed profile points.")
    if type(expected_points) is not int or expected_points <= 0:
        raise ValueError("Profile measurement requires a positive verified point count.")
    tolerances = tuple(min(MAX_SNAP_DISTANCE,
                           max(.025, source_pick_tolerance(item))) for item in requests)
    best = [None, None]
    scanned = 0
    started = monotonic()
    for chunk in chunks:
        if cancelled():
            raise InterruptedError("Profile measurement cancelled; saved measurements are unchanged.")
        names = set(chunk.dtype.names or ())
        required = {"X", "Y", "Z"}
        if profile.vertical_axis == "HeightAboveGround":
            required.add("HeightAboveGround")
        if required - names:
            raise ValueError("Source lacks profile measurement dimensions: "
                             + ", ".join(sorted(required-names)) + ".")
        x = np.asarray(chunk["X"], dtype="f8")
        y = np.asarray(chunk["Y"], dtype="f8")
        z = np.asarray(chunk["Z"], dtype="f8")
        vertical = (np.asarray(chunk["HeightAboveGround"], dtype="f8")
                    if profile.vertical_axis == "HeightAboveGround" else z)
        from .profile import profile_coordinates, profile_membership
        along, cross, _distance = profile_coordinates(profile, x, y, np)
        finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & np.isfinite(vertical)
        eligible = finite & profile_membership(profile, x, y, np)
        if profile.vertical_limits is not None:
            eligible &= ((vertical >= profile.vertical_limits[0])
                         & (vertical <= profile.vertical_limits[1]))
        for index, request in enumerate(requests):
            if profile.display_projection == "PROFILE_DISTANCE":
                distance2 = ((along-request[0])**2+(cross-request[1])**2
                             +(vertical-request[2])**2)
            else:
                distance2 = ((x-request[0])**2+(y-request[1])**2
                             +(vertical-request[2])**2)
            if not len(distance2):
                continue
            distance2 = np.where(eligible, distance2, np.inf)
            location = int(np.argmin(distance2))
            candidate = float(distance2[location])
            if math.isfinite(candidate) and (best[index] is None or candidate < best[index][0]):
                hag = (float(chunk["HeightAboveGround"][location])
                       if "HeightAboveGround" in names else None)
                if hag is not None and not math.isfinite(hag):
                    hag = None
                best[index] = (candidate, location, float(x[location]), float(y[location]),
                               float(z[location]), float(vertical[location]),
                               float(along[location]), float(cross[location]),
                               (int(chunk["Classification"][location])
                                if "Classification" in names else None), hag)
        scanned += len(chunk)
        progress(scanned)
    if scanned != expected_points:
        raise ValueError("Profile measurement source count differs from the verified header.")
    anchors = []
    for request, tolerance, candidate in zip(requests, tolerances, best):
        if candidate is None or math.sqrt(candidate[0]) > tolerance:
            raise ValueError("A profile pick could not be matched to an original source point.")
        display_xyz = ((candidate[6],candidate[7],candidate[5])
                       if profile.display_projection == "PROFILE_DISTANCE"
                       else (candidate[2],candidate[3],candidate[5]))
        anchors.append(ProfileAnchor(request,
            (candidate[2],candidate[3],candidate[4]),
            display_xyz,
            (candidate[6],candidate[5]), candidate[7], math.sqrt(candidate[0]),
            candidate[8], candidate[9]))
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


def create_profile_measurement(source_sha256, source_crs, view_id, view_name,
                               profile_geometry, anchors, *, horizontal_unit,
                               vertical_unit=None, unit_warning="", resolution_seconds=0,
                               source_point_count=1, measurement_id=None, created_at=None,
                               purpose="CROSS_SECTION"):
    from .workspace import SliceGeometry
    profile = (profile_geometry if isinstance(profile_geometry, SliceGeometry)
               else SliceGeometry(**profile_geometry))
    items = tuple(anchors)
    if len(items) != 2 or any(not isinstance(item, ProfileAnchor) for item in items):
        raise ValueError("Cross-section measurement requires two resolved profile anchors.")
    along = abs(items[1].profile_position[0]-items[0].profile_position[0])
    vertical = items[1].profile_position[1]-items[0].profile_position[1]
    if purpose == "TREE_HEIGHT" and vertical == 0:
        raise ValueError("Tree height requires distinct base and top heights.")
    if purpose == "TREE_HEIGHT":
        lower = min(item.profile_position[1] for item in items)
        if profile.vertical_axis == "HeightAboveGround" and not -1 <= lower <= 1:
            warning = (f"Lower pick is {lower:,.3f} {vertical_unit or horizontal_unit} HAG; "
                       "verify that it represents the tree base.")
            unit_warning = (unit_warning + " " + warning).strip()
        elif profile.vertical_axis == "Z":
            unit_warning = (unit_warning +
                " Elevation-based tree height depends on selecting a valid base point.").strip()
    return ProfileMeasurement(measurement_id or uuid4().hex, source_sha256,
        source_crs, view_id, view_name, asdict(profile), items[0], items[1],
        along, abs(vertical), vertical, math.hypot(along, vertical), horizontal_unit,
        vertical_unit or horizontal_unit, profile.vertical_axis, unit_warning,
        resolution_seconds, source_point_count,
        created_at or datetime.now(timezone.utc).isoformat(), purpose=purpose)


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


def resolve_source_anchors(source, expected_points, requested_points, *, pdal_module=None,
                           cancelled=lambda: False, progress=lambda count: None):
    """Resolve one or more renderer picks against the immutable original source."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    source.verify(cancelled=cancelled)
    reader = {"type":"readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename":source.path}
    chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=65_536, prefetch=0)
    anchors, duration = resolve_anchor_chunks(chunks, expected_points, requested_points,
                                              cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    return anchors, duration


def resolve_source_profile_measurement(source, expected_points, requested_points,
                                       source_crs, profile_geometry, view_id, view_name, *,
                                       pdal_module=None, crs_type=None,
                                       cancelled=lambda: False, progress=lambda count: None,
                                       purpose="CROSS_SECTION"):
    """Resolve two picks from one Vertical Slice against original source records."""
    from .workspace import SliceGeometry
    profile = (profile_geometry if isinstance(profile_geometry, SliceGeometry)
               else SliceGeometry(**profile_geometry))
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    if crs_type is None:
        from pyproj import CRS
        crs_type = CRS
    if source_crs.startswith("SOURCE_LOCAL:"):
        if profile.crs != source_crs:
            raise ValueError("Profile and source-local coordinate identities do not match.")
    elif not crs_type.from_user_input(source_crs).equals(crs_type.from_user_input(profile.crs)):
        raise ValueError("Profile and original source CRS do not match.")
    source.verify(cancelled=cancelled)
    reader = {"type":"readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename":source.path}
    chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=65_536,prefetch=0)
    anchors, duration = resolve_profile_anchor_chunks(chunks, expected_points,
        requested_points, profile, cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    horizontal, vertical, warning = measurement_unit_context(source_crs, crs_type)
    if profile.vertical_axis == "HeightAboveGround":
        axis_warning = "Vertical values use the stored HeightAboveGround dimension."
        warning = (warning + " " + axis_warning).strip()
    return create_profile_measurement(source.sha256, source_crs, view_id, view_name,
        profile, anchors, horizontal_unit=horizontal, vertical_unit=vertical,
        unit_warning=warning, resolution_seconds=duration,
        source_point_count=expected_points, purpose=purpose)


def measurement_summary(measurement):
    item = measurement if isinstance(measurement, (PointMeasurement, AreaMeasurement, ProfileMeasurement)) else measurement_from_dict(measurement)
    if isinstance(item, ProfileMeasurement):
        axis = "HAG" if item.vertical_axis == "HeightAboveGround" else "Elevation"
        if item.purpose == "TREE_HEIGHT":
            return (f"Tree height {item.vertical_distance:,.3f} {item.vertical_unit} | "
                    f"Horizontal offset {item.along_distance:,.3f} {item.horizontal_unit} | "
                    f"Basis {axis}")
        return (f"Cross-section {item.cross_section_distance:,.3f} {item.horizontal_unit} | "
                f"Along {item.along_distance:,.3f} {item.horizontal_unit} | "
                f"{axis} change {item.vertical_difference:+,.3f} {item.vertical_unit}")
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
        if values.get("kind") == "PROFILE_DISTANCE":
            values["start"] = ProfileAnchor(**values["start"])
            values["end"] = ProfileAnchor(**values["end"])
            return ProfileMeasurement(**values)
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
