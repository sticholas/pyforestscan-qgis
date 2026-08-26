"""Durable file-to-file PBM preparation for large standalone sources."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment, ClassificationInspectionService
from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode, HeightNormalizationPlanner, build_preparation_assessment, preparation_recommendations
from pyforestscan_qgis.core.lidar_preparation_execution import checkpoint_is_compatible
from pyforestscan_qgis.core.point_dimensions import PointDimensionCapabilities
from pyforestscan_qgis.core.source_coordinate_units import assess_source_coordinate_units


@dataclass(frozen=True)
class PreparedSourceResult:
    request: object
    plan: object
    provenance_path: Path
    reused: bool


def prepare_request_source(spec, request, *, progress=None) -> PreparedSourceResult | None:
    """Create/reuse one prepared LAZ before product arrays enter Python memory."""
    if spec.product not in {"chm", "rumple"}:
        return None
    if any(getattr(request, name, None) for name in ("bounds", "crop_polygon", "crop_polygon_path", "polygon_execution_input")):
        return None
    dimensions = PointDimensionCapabilities.from_names(getattr(request, "source_dimensions", ()))
    if dimensions.has_existing_hag:
        return None
    units = assess_source_coordinate_units(getattr(request, "crs", None), getattr(request, "source_coordinate_units", ""))
    fingerprint = _source_fingerprint(Path(request.input_path))
    classification_path = spec.run_folder / "preparation" / f"classification_{fingerprint}.json"
    classification = _read_classification(classification_path)
    if classification is None:
        _notify(progress, "Inspecting Ground Returns")
        classification = ClassificationInspectionService().inspect(
            Path(request.input_path),
            point_count=getattr(request, "source_point_count", None),
        )
        _write_json(classification_path, classification.to_dict())
    else:
        _notify(progress, "Reusing Ground Inspection")
    if not dimensions.names:
        dimensions = PointDimensionCapabilities.from_names(classification.observed_dimensions)
    spatial_mode = "resolved" if getattr(request, "crs", None) else "source_local"
    assessment = build_preparation_assessment(
        source=request.input_path,
        spatial_reference_mode=spatial_mode,
        crs=getattr(request, "crs", None),
        coordinate_units=units,
        dimensions=dimensions.names,
        classification=classification,
        dtm_path=getattr(request, "dtm_path", None),
        requested_products=(spec.product,),
        point_count=getattr(request, "source_point_count", None),
    )
    plan = HeightNormalizationPlanner().plan(assessment, checkpoint_root=spec.run_folder / "preparation")
    plan_path = spec.run_folder / "preparation" / plan.signature / "preparation_plan.json"
    recommendations = preparation_recommendations(assessment, plan)
    _write_json(plan_path, {"assessment": _assessment_dict(assessment), "plan": _plan_dict(plan), "recommendations": asdict(recommendations)})
    if not plan.can_execute:
        raise RuntimeError("; ".join(plan.blockers))
    if plan.height_mode is HeightNormalizationPlanMode.USE_EXISTING_HAG:
        return None
    artifact = plan.prepared_artifact
    if artifact is None:
        raise RuntimeError("PREPARATION_VALIDATION_FAILED: prepared artifact path was not planned.")
    provenance_path = artifact.parent / "preparation_provenance.json"
    if checkpoint_is_compatible(artifact, plan.signature):
        return PreparedSourceResult(_prepared_request(request, artifact), plan, provenance_path, True)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    temporary = artifact.with_name(artifact.stem + ".partial" + artifact.suffix)
    _notify(progress, "Preparing Ground Classification" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "Generating Height Above Ground")
    pipeline_json = _pipeline(assessment, plan, temporary)
    import pdal
    pipeline = pdal.Pipeline(json.dumps({"pipeline": pipeline_json}))
    pipeline.execute()
    if not temporary.is_file() or temporary.stat().st_size <= 0:
        raise RuntimeError("PREPARATION_VALIDATION_FAILED: PDAL did not create the prepared LiDAR artifact.")
    temporary.replace(artifact)
    provenance = {
        "job_identity": spec.job_id,
        "source": str(assessment.source),
        "source_fingerprint": assessment.source_fingerprint,
        "original_dimensions": list(assessment.dimensions.names),
        "original_crs_status": assessment.spatial_reference_mode,
        "coordinate_units": assessment.coordinate_units.units.value,
        "classification_assessment": classification.to_dict(),
        "ground_method": "automatic_smrf" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "existing_class_2",
        "hag_method": "generated_ground_then_delaunay" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "delaunay" if plan.height_mode is HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND else "dtm",
        "dtm": str(assessment.dtm_path or ""),
        "parameters": {"canonical_metres": {"smrf_cell": 1.0, "smrf_threshold": 0.5, "smrf_window": 18.0}, "source_unit_factor": assessment.coordinate_units.from_meters(1.0)},
        "output_dimensions": [*assessment.dimensions.names, "HeightAboveGround"],
        "warnings": list(plan.warnings),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preparation_signature": plan.signature,
        "recommendations": asdict(recommendations),
    }
    _write_json(provenance_path, provenance)
    _write_json(artifact.with_suffix(".checkpoint.json"), {"signature": plan.signature, "provenance": str(provenance_path), "complete": True})
    return PreparedSourceResult(_prepared_request(request, artifact), plan, provenance_path, False)


def _pipeline(assessment, plan, output):
    source = str(assessment.source)
    reader = "readers.ept" if source.lower().endswith("ept.json") else "readers.copc" if source.lower().endswith((".copc", ".copc.laz")) else "readers.las"
    stages = [{"type": reader, "filename": source}]
    if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY:
        scale = assessment.coordinate_units.from_meters(1.0)
        stages.append({"type": "filters.smrf", "ignore": "Classification[7:7]", "cell": 1.0 * scale, "scalar": 1.25, "slope": 0.15, "threshold": 0.5 * scale, "window": 18.0 * scale, "returns": "last,only"})
    if plan.height_mode is HeightNormalizationPlanMode.DTM_EXISTING:
        stages.append({"type": "filters.hag_dem", "raster": str(assessment.dtm_path)})
    else:
        stages.append({"type": "filters.hag_delaunay"})
    writer = {"type": "writers.las", "filename": str(output), "compression": "laszip", "extra_dims": "all"}
    if assessment.crs:
        writer["a_srs"] = assessment.crs
    stages.append(writer)
    return stages


def _prepared_request(request, artifact):
    fields = getattr(request, "__dataclass_fields__", {})
    values = {"input_path": artifact, "source_dimensions": tuple(dict.fromkeys((*getattr(request, "source_dimensions", ()), "HeightAboveGround")))}
    if "hag_method" in fields:
        values["hag_method"] = "existing_normalized_height"
    if "hag_source_dimension" in fields:
        values["hag_source_dimension"] = "HeightAboveGround"
    return replace(request, **values)


def _assessment_dict(value):
    return {"source": str(value.source), "source_fingerprint": value.source_fingerprint, "spatial_reference_mode": value.spatial_reference_mode, "crs": value.crs, "coordinate_units": asdict(value.coordinate_units), "dimensions": value.dimensions.to_dict(), "classification": value.classification.to_dict() if value.classification else None, "dtm_path": str(value.dtm_path or ""), "requested_products": list(value.requested_products), "point_count": value.point_count}


def _plan_dict(value):
    return {"readiness": value.readiness.value, "recovery": value.recovery.value, "height_mode": value.height_mode.value, "steps": [asdict(step) for step in value.steps], "warnings": list(value.warnings), "blockers": list(value.blockers), "signature": value.signature, "prepared_artifact": str(value.prepared_artifact or ""), "large_source": value.large_source}


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _source_fingerprint(path: Path) -> str:
    from pyforestscan_qgis.core.lidar_preparation import source_fingerprint
    return source_fingerprint(path)


def _read_classification(path: Path) -> ClassificationAssessment | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        counts = tuple((int(item["classification"]), int(item["count"])) for item in value.get("class_counts", ()))
        return ClassificationAssessment(
            bool(value.get("classification_present")), int(value.get("sampled_points", 0)),
            bool(value.get("ground_class_2_observed")), value.get("ground_fraction_estimate"),
            tuple(int(item) for item in value.get("vegetation_classes_observed", ())),
            str(value.get("confidence", "UNKNOWN")), str(value.get("sampling_method", "cached bounded sample")),
            tuple(str(item) for item in value.get("warnings", ())), counts,
            tuple(str(item) for item in value.get("observed_dimensions", ())),
            int(value.get("strata_sampled", 0)), int(value.get("strata_with_ground", 0)),
            value.get("ground_coverage_ratio"), str(value.get("ground_coverage_confidence", "UNKNOWN")),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _notify(callback, message):
    if callback:
        callback(message)
