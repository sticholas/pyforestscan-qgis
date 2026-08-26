"""Authoritative assessment and planning for non-destructive LiDAR preparation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .classification_inspection import ClassificationAssessment
from .point_dimensions import PointDimensionCapabilities
from .source_coordinate_units import SourceCoordinateUnitAssessment, SourceCoordinateUnits


HAG_PRODUCTS = frozenset({"chm", "rumple", "pad", "pai", "fhd", "canopy_cover", "voxel_stat"})


class PreparationReadiness(str, Enum):
    READY = "READY"
    READY_AFTER_PREPARATION = "READY_AFTER_PREPARATION"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    BLOCKED = "BLOCKED"


class PreparationRecoveryDecision(str, Enum):
    AUTOMATICALLY_RECOVERED = "AUTOMATICALLY_RECOVERED"
    RECOVERED_WITH_WARNING = "RECOVERED_WITH_WARNING"
    USER_INPUT_REQUIRED = "USER_INPUT_REQUIRED"
    SCIENTIFICALLY_BLOCKED = "SCIENTIFICALLY_BLOCKED"


class HeightNormalizationPlanMode(str, Enum):
    USE_EXISTING_HAG = "USE_EXISTING_HAG"
    DTM_EXISTING = "DTM_EXISTING"
    DELAUNAY_FROM_EXISTING_GROUND = "DELAUNAY_FROM_EXISTING_GROUND"
    AUTO_CLASSIFY_GROUND_THEN_DELAUNAY = "AUTO_CLASSIFY_GROUND_THEN_DELAUNAY"
    AUTO_GENERATE_DTM_THEN_HAG = "AUTO_GENERATE_DTM_THEN_HAG"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class LidarPreparationAssessment:
    source: Path
    source_fingerprint: str
    spatial_reference_mode: str
    crs: str | None
    coordinate_units: SourceCoordinateUnitAssessment
    dimensions: PointDimensionCapabilities
    classification: ClassificationAssessment | None
    dtm_path: Path | None
    requested_products: tuple[str, ...]
    point_count: int | None = None


@dataclass(frozen=True)
class LidarPreparationStep:
    step_id: str
    label: str
    method: str
    checkpointable: bool = False


@dataclass(frozen=True)
class LidarPreparationPlan:
    readiness: PreparationReadiness
    recovery: PreparationRecoveryDecision
    height_mode: HeightNormalizationPlanMode
    steps: tuple[LidarPreparationStep, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    signature: str
    prepared_artifact: Path | None = None
    large_source: bool = False

    @property
    def can_execute(self) -> bool:
        return self.readiness in {PreparationReadiness.READY, PreparationReadiness.READY_AFTER_PREPARATION}


@dataclass(frozen=True)
class PreparedLidarCapabilities:
    dimensions: PointDimensionCapabilities
    has_valid_hag: bool
    classification: ClassificationAssessment | None
    prepared_path: Path | None
    preparation_signature: str


@dataclass(frozen=True)
class HagSpatialContextRequirement:
    """Ground context required around tiled product cores."""

    core_buffer_source_units: float
    policy: str = "read buffered points, normalize once, retain core"
    seam_validation_required: bool = True


@dataclass(frozen=True)
class LidarPreparationRecommendations:
    observed: tuple[str, ...]
    recommendations: tuple[str, ...]
    blocking_actions: tuple[str, ...] = ()


def preparation_recommendations(assessment: LidarPreparationAssessment, plan: LidarPreparationPlan) -> LidarPreparationRecommendations:
    observed: list[str] = []
    recommendations: list[str] = []
    if not assessment.crs:
        observed.append("CRS metadata is missing.")
        recommendations.append("Assign a trusted CRS to improve spatial interoperability.")
    if not assessment.dimensions.has_existing_hag:
        observed.append("HeightAboveGround is missing.")
        recommendations.append("Retain the prepared HAG checkpoint when this source will be reused.")
    if not assessment.classification or not assessment.classification.ground_class_2_observed:
        observed.append("Reliable class-2 ground was not confirmed before planning.")
        recommendations.append("Review automatic ground classification or provide a compatible DTM.")
    if "Intensity" in assessment.dimensions.names:
        observed.append("Intensity is available.")
    if {"Red", "Green", "Blue"}.issubset(assessment.dimensions.names):
        observed.append("RGB is available.")
    return LidarPreparationRecommendations(tuple(observed), tuple(recommendations), tuple(plan.blockers))


class HeightNormalizationPlanner:
    """Choose the least invasive defensible HAG strategy."""

    def plan(self, assessment: LidarPreparationAssessment, *, checkpoint_root: Path | None = None) -> LidarPreparationPlan:
        needs_hag = bool(HAG_PRODUCTS.intersection(assessment.requested_products))
        if not needs_hag:
            return _plan(assessment, PreparationReadiness.READY, PreparationRecoveryDecision.AUTOMATICALLY_RECOVERED, HeightNormalizationPlanMode.USE_EXISTING_HAG, (), (), checkpoint_root)
        if assessment.dimensions.has_existing_hag:
            return _plan(assessment, PreparationReadiness.READY, PreparationRecoveryDecision.AUTOMATICALLY_RECOVERED, HeightNormalizationPlanMode.USE_EXISTING_HAG, (), (), checkpoint_root)
        if not {"X", "Y", "Z"}.issubset(assessment.dimensions.names):
            return _plan(assessment, PreparationReadiness.BLOCKED, PreparationRecoveryDecision.SCIENTIFICALLY_BLOCKED, HeightNormalizationPlanMode.UNAVAILABLE, (), ("Valid X, Y, and Z dimensions are required.",), checkpoint_root)
        if assessment.dtm_path:
            return _plan(assessment, PreparationReadiness.READY_AFTER_PREPARATION, PreparationRecoveryDecision.AUTOMATICALLY_RECOVERED, HeightNormalizationPlanMode.DTM_EXISTING, (LidarPreparationStep("hag_dtm", "Generating Height Above Ground", "PyForestScan/PDAL DTM HAG", True),), (), checkpoint_root)
        if not assessment.coordinate_units.distance_operations_safe:
            return _plan(assessment, PreparationReadiness.NEEDS_USER_INPUT, PreparationRecoveryDecision.USER_INPUT_REQUIRED, HeightNormalizationPlanMode.UNAVAILABLE, (), ("SOURCE_UNITS_UNKNOWN: assign trusted source units or a CRS before distance-based ground/HAG preparation.",), checkpoint_root)
        classification = assessment.classification
        if classification and classification.ground_class_2_observed:
            return _plan(assessment, PreparationReadiness.READY_AFTER_PREPARATION, PreparationRecoveryDecision.AUTOMATICALLY_RECOVERED, HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND, (LidarPreparationStep("hag_delaunay", "Generating Height Above Ground", "PyForestScan/PDAL Delaunay HAG", True),), tuple(classification.warnings), checkpoint_root)
        if assessment.dimensions.names and "Classification" in assessment.dimensions.names:
            steps = (
                LidarPreparationStep("classify_ground", "Preparing Ground Classification", "PyForestScan/PDAL SMRF", True),
                LidarPreparationStep("hag_delaunay", "Generating Height Above Ground", "PyForestScan/PDAL Delaunay HAG", True),
            )
            return _plan(assessment, PreparationReadiness.READY_AFTER_PREPARATION, PreparationRecoveryDecision.RECOVERED_WITH_WARNING, HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY, steps, ("Existing class 2 was not confirmed; automatic SMRF classification will be validated before HAG.",), checkpoint_root)
        return _plan(assessment, PreparationReadiness.BLOCKED, PreparationRecoveryDecision.SCIENTIFICALLY_BLOCKED, HeightNormalizationPlanMode.UNAVAILABLE, (), ("GROUND_CLASS_UNAVAILABLE: no classification dimension, compatible DTM, or validated automatic path is available.",), checkpoint_root)


def build_preparation_assessment(*, source: Path | str, spatial_reference_mode: str, coordinate_units: SourceCoordinateUnitAssessment, dimensions: Iterable[object], classification: ClassificationAssessment | None, dtm_path: Path | None, requested_products: Iterable[object], point_count: int | None = None, crs: str | None = None) -> LidarPreparationAssessment:
    path = Path(source)
    return LidarPreparationAssessment(path, source_fingerprint(path), spatial_reference_mode, crs, coordinate_units, PointDimensionCapabilities.from_names(dimensions), classification, dtm_path, tuple(str(getattr(item, "value", item)) for item in requested_products), point_count)


def source_fingerprint(path: Path) -> str:
    try:
        stat = path.stat()
        value = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        value = str(path)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _plan(assessment, readiness, recovery, mode, steps, messages, checkpoint_root):
    basis = {"source": assessment.source_fingerprint, "spatial_mode": assessment.spatial_reference_mode, "units": assessment.coordinate_units.units.value, "height_mode": mode.value, "steps": [asdict(step) for step in steps], "dtm": str(assessment.dtm_path or ""), "version": "phase31a-v1"}
    signature = hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()
    artifact = (checkpoint_root / signature / "prepared_hag.laz") if checkpoint_root and mode is not HeightNormalizationPlanMode.USE_EXISTING_HAG else None
    return LidarPreparationPlan(readiness, recovery, mode, tuple(steps), tuple(messages) if readiness is not PreparationReadiness.BLOCKED else (), tuple(messages) if readiness in {PreparationReadiness.BLOCKED, PreparationReadiness.NEEDS_USER_INPUT} else (), signature, artifact, bool((assessment.point_count or 0) >= 20_000_000))
