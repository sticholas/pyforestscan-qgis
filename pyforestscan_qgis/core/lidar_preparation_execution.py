"""PBM-side execution, validation, provenance, and checkpoint reuse for preparation."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .classification_inspection import ClassificationAssessment, assessment_from_array
from .lidar_preparation import HeightNormalizationPlanMode, LidarPreparationAssessment, LidarPreparationPlan, PreparedLidarCapabilities
from .point_dimensions import PointDimensionCapabilities


@dataclass(frozen=True)
class HagQualityAssessment:
    valid: bool
    value_count: int
    finite_fraction: float
    minimum: float | None
    maximum: float | None
    median: float | None
    negative_fraction: float
    ground_median: float | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LidarPreparationProvenance:
    job_identity: str
    source: str
    source_fingerprint: str
    original_dimensions: tuple[str, ...]
    original_crs_status: str
    coordinate_units: str
    classification_assessment: dict[str, object] | None
    ground_method: str
    hag_method: str
    dtm: str
    parameters: dict[str, object]
    software_versions: dict[str, str]
    output_dimensions: tuple[str, ...]
    quality: dict[str, object]
    warnings: tuple[str, ...]
    timestamp: str
    preparation_signature: str


@dataclass(frozen=True)
class PreparationExecutionResult:
    arrays: tuple[object, ...]
    capabilities: PreparedLidarCapabilities
    quality: HagQualityAssessment
    provenance_path: Path
    reused_checkpoint: bool = False


def execute_preparation(
    arrays: tuple[object, ...],
    assessment: LidarPreparationAssessment,
    plan: LidarPreparationPlan,
    *,
    run_folder: Path,
    job_identity: str,
    filters_module: object,
    handlers_module: object | None = None,
    progress: Callable[[str], None] | None = None,
) -> PreparationExecutionResult:
    """Execute one selected method without modifying the source."""
    if not plan.can_execute:
        raise RuntimeError("; ".join(plan.blockers) or "No scientifically valid LiDAR preparation path is available.")
    prepared = arrays
    classification = assessment.classification
    ground_method = "existing"
    hag_method = "existing"
    if plan.height_mode is HeightNormalizationPlanMode.DTM_EXISTING:
        _notify(progress, "Generating Height Above Ground")
        prepared = tuple(filters_module.add_height_above_ground(prepared, method="dtm", dtm=str(assessment.dtm_path)))
        hag_method = "dtm"
    elif plan.height_mode is HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND:
        _notify(progress, "Generating Height Above Ground")
        prepared = tuple(filters_module.add_height_above_ground(prepared, method="delaunay"))
        hag_method = "delaunay"
    elif plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY:
        _notify(progress, "Preparing Ground Classification")
        prepared = tuple(filters_module.classify_ground_points(prepared))
        classification = assessment_from_array(_merge_arrays(prepared))
        if not classification.ground_class_2_observed:
            raise RuntimeError("GROUND_CLASSIFICATION_FAILED: automatic SMRF classification did not produce usable class-2 ground points.")
        _notify(progress, "Generating Height Above Ground")
        prepared = tuple(filters_module.add_height_above_ground(prepared, method="delaunay"))
        ground_method = "automatic_smrf"
        hag_method = "generated_ground_then_delaunay"
    merged = _merge_arrays(prepared)
    quality = validate_hag_quality(merged)
    if not quality.valid:
        raise RuntimeError("PREPARATION_VALIDATION_FAILED: " + "; ".join(quality.warnings))
    capabilities = PreparedLidarCapabilities(PointDimensionCapabilities.from_names(merged.dtype.names), True, classification, plan.prepared_artifact, plan.signature)
    provenance = LidarPreparationProvenance(
        job_identity,
        str(assessment.source),
        assessment.source_fingerprint,
        assessment.dimensions.names,
        assessment.spatial_reference_mode,
        assessment.coordinate_units.units.value,
        classification.to_dict() if classification else None,
        ground_method,
        hag_method,
        str(assessment.dtm_path or ""),
        {"smrf": {"cell": 1.0, "scalar": 1.25, "slope": 0.15, "threshold": 0.5, "window": 18.0}},
        _software_versions(filters_module),
        capabilities.dimensions.names,
        asdict(quality),
        tuple(dict.fromkeys((*plan.warnings, *quality.warnings))),
        datetime.now(timezone.utc).isoformat(),
        plan.signature,
    )
    provenance_path = run_folder / "preparation" / plan.signature / "preparation_provenance.json"
    _write_json(provenance_path, asdict(provenance))
    if plan.prepared_artifact is not None and handlers_module is not None:
        _write_prepared_checkpoint(prepared, plan.prepared_artifact, assessment, handlers_module)
        _write_json(plan.prepared_artifact.with_suffix(".checkpoint.json"), {"signature": plan.signature, "provenance": str(provenance_path), "complete": True})
    return PreparationExecutionResult(prepared, capabilities, quality, provenance_path)


def validate_hag_quality(array: object) -> HagQualityAssessment:
    names = tuple(getattr(getattr(array, "dtype", None), "names", ()) or ())
    if "HeightAboveGround" not in names:
        return HagQualityAssessment(False, len(array), 0.0, None, None, None, 0.0, None, ("HeightAboveGround dimension is missing after preparation.",))
    import numpy
    values = numpy.asarray(array["HeightAboveGround"], dtype=float)
    finite = values[numpy.isfinite(values)]
    if not len(values) or not len(finite):
        return HagQualityAssessment(False, len(values), 0.0, None, None, None, 0.0, None, ("HeightAboveGround contains no finite values.",))
    negatives = float(numpy.count_nonzero(finite < 0) / len(finite))
    ground_median = None
    if "Classification" in names:
        ground = values[numpy.asarray(array["Classification"]) == 2]
        ground = ground[numpy.isfinite(ground)]
        ground_median = float(numpy.median(ground)) if len(ground) else None
    warnings = []
    if negatives > 0.05:
        warnings.append(f"{negatives:.1%} of finite HAG values are negative; values were retained unchanged.")
    if float(numpy.max(finite) - numpy.min(finite)) <= 1e-9:
        warnings.append("HeightAboveGround is constant and cannot support forest-structure products.")
    if ground_median is not None and abs(ground_median) > 1.0:
        warnings.append("Ground-class median HeightAboveGround is more than one source unit from zero.")
    valid = len(finite) / len(values) >= 0.95 and float(numpy.max(finite) - numpy.min(finite)) > 1e-9
    return HagQualityAssessment(valid, len(values), len(finite) / len(values), float(numpy.min(finite)), float(numpy.max(finite)), float(numpy.median(finite)), negatives, ground_median, tuple(warnings))


def checkpoint_is_compatible(path: Path, signature: str) -> bool:
    marker = path.with_suffix(".checkpoint.json")
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        return path.is_file() and bool(payload.get("complete")) and payload.get("signature") == signature
    except (OSError, json.JSONDecodeError):
        return False


def _write_prepared_checkpoint(arrays, path, assessment, handlers):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".partial" + path.suffix)
    handlers.write_las(arrays, str(temporary), srs=assessment.crs or "", compress=True)
    temporary.replace(path)


def _merge_arrays(arrays):
    if len(arrays) == 1:
        return arrays[0]
    import numpy
    return numpy.concatenate(arrays)


def _software_versions(filters_module):
    import platform
    return {"python": platform.python_version(), "pyforestscan_filters": str(getattr(filters_module, "__file__", "unknown")), "preparation_contract": "phase31a-v1"}


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _notify(callback, message):
    if callback:
        callback(message)
