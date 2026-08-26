"""Central policy for trusted and assumed source-local processing units."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .source_coordinate_units import assess_source_coordinate_units
from .spatial_assignment import LinearUnit
from .spatial_selection import Bounds2D


class SpatialUnitBasis(str, Enum):
    EMBEDDED = "EMBEDDED"
    SIDECAR = "SIDECAR"
    USER_ASSIGNED = "USER_ASSIGNED"
    REPOSITORY_ASSIGNED = "REPOSITORY_ASSIGNED"
    CRS_DERIVED = "CRS_DERIVED"
    ASSUMED_SOURCE_LOCAL = "ASSUMED_SOURCE_LOCAL"
    UNRESOLVED = "UNRESOLVED"


class SourceLocalFallbackChoice(str, Enum):
    METERS = LinearUnit.METERS.value
    INTERNATIONAL_FEET = LinearUnit.INTERNATIONAL_FEET.value
    US_SURVEY_FEET = LinearUnit.US_SURVEY_FEET.value
    REQUIRE_EXPLICIT_ASSIGNMENT = "REQUIRE_EXPLICIT_ASSIGNMENT"


class PolygonAlignmentFallbackChoice(str, Enum):
    AUTOMATIC_WHEN_COMPATIBLE = "AUTOMATIC_WHEN_COMPATIBLE"
    ASK = "ASK"
    REQUIRE_EXPLICIT_CRS = "REQUIRE_EXPLICIT_CRS"


class EffectiveSpatialMode(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    USER_ASSIGNED = "USER_ASSIGNED"
    REPOSITORY_ASSIGNED = "REPOSITORY_ASSIGNED"
    SOURCE_LOCAL_ASSUMED_UNITS = "SOURCE_LOCAL_ASSUMED_UNITS"
    ASSUMED_MATCHING_COORDINATE_SPACE = "ASSUMED_MATCHING_COORDINATE_SPACE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


SOURCE_LOCAL_FALLBACK_PRODUCTS = frozenset({"chm", "rumple"})


@dataclass(frozen=True)
class SourceLocalFallbackPolicy:
    default_units: SourceLocalFallbackChoice = SourceLocalFallbackChoice.METERS
    version: int = 1
    polygon_alignment: PolygonAlignmentFallbackChoice = PolygonAlignmentFallbackChoice.AUTOMATIC_WHEN_COMPATIBLE

    @property
    def linear_unit(self) -> LinearUnit | None:
        return LinearUnit.parse(self.default_units.value)


@dataclass(frozen=True)
class ProcessingSpatialContext:
    crs: str | None
    linear_units: LinearUnit | None
    unit_basis: SpatialUnitBasis
    confidence: str
    source_units_authoritative: bool
    georeferenced: bool
    processing_coordinate_mode: str
    distance_operations_safe: bool
    fallback_applied: bool = False
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["linear_units"] = self.linear_units.value if self.linear_units else ""
        value["unit_basis"] = self.unit_basis.value
        return value


@dataclass(frozen=True)
class CoordinateSpaceCompatibility:
    raw_overlap: bool
    strong: bool
    x_overlap: float
    y_overlap: float
    relative_overlap: float
    scale_ratio: float
    magnitude_compatible: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EffectiveSpatialContext:
    mode: EffectiveSpatialMode
    raw_crs: str
    effective_crs: str
    horizontal_crs: str
    units: LinearUnit | None
    crs_basis: str
    unit_basis: SpatialUnitBasis
    assignment_scope: str
    confidence: str
    georeferenced: bool
    alignment_allowed: bool
    reprojection_allowed: bool
    provenance: str
    coordinates_transformed: bool = False
    fallback_used: bool = False
    compatibility: CoordinateSpaceCompatibility | None = None
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload["units"] = self.units.value if self.units else ""
        payload["unit_basis"] = self.unit_basis.value
        return payload


class SourceLocalFallbackPolicyStore:
    """Small user-local JSON preference store, independent of QGIS Python settings."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def read(self) -> SourceLocalFallbackPolicy:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            choice = SourceLocalFallbackChoice(str(value.get("source_local_default_units", SourceLocalFallbackChoice.METERS.value)))
            polygon = PolygonAlignmentFallbackChoice(str(value.get("unreferenced_polygon_alignment", PolygonAlignmentFallbackChoice.AUTOMATIC_WHEN_COMPATIBLE.value)))
            return SourceLocalFallbackPolicy(choice, int(value.get("version", 1)), polygon)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return SourceLocalFallbackPolicy()

    def write(self, policy: SourceLocalFallbackPolicy) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"version": policy.version, "source_local_default_units": policy.default_units.value, "unreferenced_polygon_alignment": policy.polygon_alignment.value}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)


def default_source_local_policy_store() -> SourceLocalFallbackPolicyStore:
    from .backend.paths import resolve_backend_paths
    return SourceLocalFallbackPolicyStore(resolve_backend_paths().backend_root / "spatial_policy.json")


def resolve_processing_spatial_context(
    *,
    crs: object = None,
    explicit_units: object = None,
    assignment_scope: str = "",
    resolution_source: str = "",
    requested_products: Iterable[object] = (),
    source_local_allowed: bool = True,
    polygon_alignment_required: bool = False,
    cross_source_alignment_required: bool = False,
    contradictory_evidence: bool = False,
    policy: SourceLocalFallbackPolicy | None = None,
) -> ProcessingSpatialContext:
    """Resolve one immutable context without inventing geographic meaning."""
    products = {str(getattr(item, "value", item)).casefold() for item in requested_products}
    trusted = assess_source_coordinate_units(crs, explicit_units)
    if contradictory_evidence:
        return _blocked("Conflicting authoritative spatial metadata must be resolved before processing.")
    if str(crs or "").strip():
        basis = SpatialUnitBasis.CRS_DERIVED
        if "sidecar" in resolution_source:
            basis = SpatialUnitBasis.SIDECAR
        elif resolution_source == "embedded_metadata":
            basis = SpatialUnitBasis.EMBEDDED
        elif assignment_scope:
            basis = SpatialUnitBasis.REPOSITORY_ASSIGNED if assignment_scope.upper() == "REPOSITORY" else SpatialUnitBasis.USER_ASSIGNED
        return ProcessingSpatialContext(str(crs), trusted.linear_unit, basis, trusted.confidence, True, True, "georeferenced", trusted.distance_operations_safe)
    if trusted.distance_operations_safe:
        basis = SpatialUnitBasis.REPOSITORY_ASSIGNED if assignment_scope.upper() == "REPOSITORY" else SpatialUnitBasis.USER_ASSIGNED
        return ProcessingSpatialContext(None, trusted.linear_unit, basis, "HIGH", True, False, "source_local", True)
    if polygon_alignment_required or cross_source_alignment_required:
        return _blocked("This LiDAR needs a coordinate system before it can be aligned to other spatial data.")
    eligible = bool(products) and products.issubset(SOURCE_LOCAL_FALLBACK_PRODUCTS)
    active_policy = policy or SourceLocalFallbackPolicy()
    fallback_unit = active_policy.linear_unit
    if source_local_allowed and eligible and fallback_unit is not None:
        return ProcessingSpatialContext(
            None, fallback_unit, SpatialUnitBasis.ASSUMED_SOURCE_LOCAL, "ASSUMED", False, False,
            "source_local", True, True,
            ("Source coordinate units are not encoded in the LiDAR. PyForestScan will process this standalone job in source coordinates using the configured unit fallback.",),
        )
    return _blocked("Source coordinate units require explicit assignment for this operation.")


def evaluate_coordinate_space_compatibility(source: Bounds2D, polygon: Bounds2D) -> CoordinateSpaceCompatibility:
    """Measure raw numeric compatibility without claiming CRS discovery."""
    x_overlap = max(0.0, min(source.xmax, polygon.xmax) - max(source.xmin, polygon.xmin))
    y_overlap = max(0.0, min(source.ymax, polygon.ymax) - max(source.ymin, polygon.ymin))
    raw_overlap = x_overlap > 0.0 and y_overlap > 0.0
    source_width, source_height = source.xmax - source.xmin, source.ymax - source.ymin
    polygon_width, polygon_height = polygon.xmax - polygon.xmin, polygon.ymax - polygon.ymin
    min_area = min(source_width * source_height, polygon_width * polygon_height)
    relative = (x_overlap * y_overlap / min_area) if raw_overlap and min_area > 0 else 0.0
    spans = [value for value in (source_width, source_height, polygon_width, polygon_height) if value > 0]
    scale_ratio = max(spans) / min(spans) if spans else float("inf")
    source_center = ((source.xmin + source.xmax) / 2.0, (source.ymin + source.ymax) / 2.0)
    polygon_center = ((polygon.xmin + polygon.xmax) / 2.0, (polygon.ymin + polygon.ymax) / 2.0)
    magnitude_limit = max(spans, default=1.0) * 20.0
    magnitude_compatible = abs(source_center[0] - polygon_center[0]) <= magnitude_limit and abs(source_center[1] - polygon_center[1]) <= magnitude_limit
    strong = raw_overlap and relative >= 0.01 and scale_ratio <= 10_000.0 and magnitude_compatible
    reason = "Raw envelopes overlap strongly in the same numeric coordinate space." if strong else ("Raw envelopes overlap, but compatibility is too weak for automatic assignment." if raw_overlap else "Raw envelopes do not overlap in the same numeric coordinate space.")
    return CoordinateSpaceCompatibility(raw_overlap, strong, x_overlap, y_overlap, relative, scale_ratio, magnitude_compatible, reason)


def resolve_effective_spatial_context(
    *,
    raw_crs: str = "",
    resolved_crs: str = "",
    resolution_source: str = "",
    assignment_scope: str = "",
    contradictory_evidence: bool = False,
    polygon_crs: str = "",
    source_bounds: Bounds2D | None = None,
    polygon_bounds: Bounds2D | None = None,
    polygon_alignment_required: bool = False,
    source_local_allowed: bool = False,
    requested_products: Iterable[object] = (),
    explicit_units: object = None,
    policy: SourceLocalFallbackPolicy | None = None,
) -> EffectiveSpatialContext:
    """Resolve one provenance-rich spatial interpretation for every entry mode."""
    active_policy = policy or SourceLocalFallbackPolicy()
    compatibility = evaluate_coordinate_space_compatibility(source_bounds, polygon_bounds) if source_bounds and polygon_bounds else None
    if contradictory_evidence:
        return EffectiveSpatialContext(EffectiveSpatialMode.CONFLICT, raw_crs, "", "", None, "conflict", SpatialUnitBasis.UNRESOLVED, assignment_scope, "NONE", False, False, False, "conflicting_spatial_evidence", compatibility=compatibility, blockers=("Conflicting authoritative spatial metadata must be resolved before processing.",))
    effective = str(resolved_crs or raw_crs or "").strip()
    if effective:
        units = assess_source_coordinate_units(effective, explicit_units).linear_unit
        assigned = bool(assignment_scope or "assignment" in resolution_source.casefold())
        repository_assigned = assignment_scope.upper() == "REPOSITORY" or "repository" in resolution_source.casefold()
        mode = EffectiveSpatialMode.REPOSITORY_ASSIGNED if repository_assigned else (EffectiveSpatialMode.USER_ASSIGNED if assigned else EffectiveSpatialMode.AUTHORITATIVE)
        basis = SpatialUnitBasis.REPOSITORY_ASSIGNED if repository_assigned else (SpatialUnitBasis.USER_ASSIGNED if assigned else SpatialUnitBasis.CRS_DERIVED)
        return EffectiveSpatialContext(mode, raw_crs, effective, effective, units, resolution_source or "embedded_metadata", basis, assignment_scope, "HIGH", True, True, True, resolution_source or "embedded_metadata", compatibility=compatibility)
    if polygon_alignment_required and polygon_crs and compatibility and compatibility.strong and active_policy.polygon_alignment is PolygonAlignmentFallbackChoice.AUTOMATIC_WHEN_COMPATIBLE:
        units = assess_source_coordinate_units(polygon_crs).linear_unit
        return EffectiveSpatialContext(
            EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE, raw_crs, polygon_crs, polygon_crs, units,
            "assumed_matching_coordinate_space", SpatialUnitBasis.CRS_DERIVED, "", "ASSUMED", True, True, False,
            "polygon_coordinate_space_fallback", False, True, compatibility,
            (f"The LiDAR has no CRS metadata. Its coordinates strongly match the polygon coordinate space and will be interpreted as {polygon_crs} without reprojection.",),
        )
    if polygon_alignment_required:
        reason = compatibility.reason if compatibility else "Raw coordinate compatibility could not be evaluated."
        return EffectiveSpatialContext(EffectiveSpatialMode.UNRESOLVED, raw_crs, "", "", None, "unresolved", SpatialUnitBasis.UNRESOLVED, "", "NONE", False, False, False, "unresolved", compatibility=compatibility, blockers=(f"This LiDAR needs a coordinate system before polygon alignment. {reason}",))
    base = resolve_processing_spatial_context(crs=None, explicit_units=explicit_units, requested_products=requested_products, source_local_allowed=source_local_allowed, policy=active_policy)
    if base.fallback_applied:
        return EffectiveSpatialContext(EffectiveSpatialMode.SOURCE_LOCAL_ASSUMED_UNITS, raw_crs, "", "", base.linear_units, "source_local", base.unit_basis, assignment_scope, base.confidence, False, False, False, "source_local_assumed_units", False, True, compatibility, base.warnings, base.blockers)
    return EffectiveSpatialContext(EffectiveSpatialMode.UNRESOLVED, raw_crs, "", "", base.linear_units, "unresolved", base.unit_basis, assignment_scope, base.confidence, False, False, False, "unresolved", compatibility=compatibility, warnings=base.warnings, blockers=base.blockers)


def processing_spatial_context_from_dict(value: dict[str, object]) -> ProcessingSpatialContext:
    """Rehydrate an immutable prerun decision without policy re-resolution."""
    return ProcessingSpatialContext(
        str(value.get("crs")) if value.get("crs") else None,
        LinearUnit.parse(value.get("linear_units")),
        SpatialUnitBasis(str(value.get("unit_basis", SpatialUnitBasis.UNRESOLVED.value))),
        str(value.get("confidence", "NONE")),
        bool(value.get("source_units_authoritative")), bool(value.get("georeferenced")),
        str(value.get("processing_coordinate_mode", "unresolved")), bool(value.get("distance_operations_safe")),
        bool(value.get("fallback_applied")), tuple(str(item) for item in value.get("warnings", ()) or ()), tuple(str(item) for item in value.get("blockers", ()) or ()),
    )


def _blocked(message: str) -> ProcessingSpatialContext:
    return ProcessingSpatialContext(None, None, SpatialUnitBasis.UNRESOLVED, "NONE", False, False, "unresolved", False, blockers=(message,))


__all__ = [
    "CoordinateSpaceCompatibility", "EffectiveSpatialContext", "EffectiveSpatialMode", "PolygonAlignmentFallbackChoice", "ProcessingSpatialContext", "SOURCE_LOCAL_FALLBACK_PRODUCTS", "SourceLocalFallbackChoice",
    "SourceLocalFallbackPolicy", "SourceLocalFallbackPolicyStore", "SpatialUnitBasis",
    "default_source_local_policy_store", "evaluate_coordinate_space_compatibility", "processing_spatial_context_from_dict", "resolve_effective_spatial_context", "resolve_processing_spatial_context",
]
