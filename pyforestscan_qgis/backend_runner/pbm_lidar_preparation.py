"""Durable file-to-file PBM preparation for large standalone sources."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from pyforestscan_qgis.core.classification_inspection import ClassificationAssessment, ClassificationInspectionService
from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode, HeightNormalizationPlanner, build_preparation_assessment, preparation_recommendations
from pyforestscan_qgis.core.lidar_preparation_execution import checkpoint_is_compatible
from pyforestscan_qgis.core.point_dimensions import PointDimensionCapabilities
from pyforestscan_qgis.core.source_coordinate_units import assess_processing_coordinate_units


@dataclass(frozen=True)
class PreparedSourceResult:
    request: object
    plan: object
    provenance_path: Path
    reused: bool
    status_path: Path | None = None
    quality: dict[str, object] | None = None


def prepare_request_source(spec, request, *, progress=None, preparation_bounds=None, normalized_z_candidate=False, runtime_contract=None) -> PreparedSourceResult | None:
    """Create/reuse one prepared LAZ before product arrays enter Python memory."""
    if spec.product not in {"chm", "rumple"}:
        return None
    if preparation_bounds is None and any(getattr(request, name, None) for name in ("bounds", "crop_polygon", "crop_polygon_path", "polygon_execution_input")):
        return None
    dimensions = PointDimensionCapabilities.from_names(getattr(request, "source_dimensions", ()))
    if dimensions.has_existing_hag:
        return None
    units = assess_processing_coordinate_units(getattr(request, "crs", None), getattr(request, "source_coordinate_units", ""), getattr(request, "source_units_basis", "UNRESOLVED"))
    fingerprint = _source_fingerprint(Path(request.input_path))
    normalized_quality = _inspect_normalized_z(Path(request.input_path), preparation_bounds) if normalized_z_candidate else None
    classification_path = spec.run_folder / "preparation" / f"classification_{fingerprint}.json"
    classification = None
    if normalized_quality and (normalized_quality.get("valid") or normalized_quality.get("existing_hag")):
        dimensions = PointDimensionCapabilities.from_names(normalized_quality.get("observed_dimensions", ()))
        _notify(progress, "Validated Existing Height Data")
    else:
        classification = _read_classification(classification_path)
        if classification is None:
            _notify(progress, "Inspecting Ground Returns")
            classification = ClassificationInspectionService().inspect(
                Path(request.input_path),
                point_count=getattr(request, "source_point_count", None),
                bounds=preparation_bounds,
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
        normalized_z_validated=bool(normalized_quality and normalized_quality.get("valid") and not normalized_quality.get("existing_hag")),
    )
    plan = HeightNormalizationPlanner().plan(assessment, checkpoint_root=spec.run_folder / "preparation")
    plan = _scope_plan(plan, spec.run_folder / "preparation", preparation_bounds, runtime_contract)
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
        return PreparedSourceResult(_prepared_request(request, artifact), plan, provenance_path, True, quality=normalized_quality)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    temporary = artifact.with_name(artifact.stem + ".partial" + artifact.suffix)
    _notify(progress, "Preparing Ground Classification" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "Generating Height Above Ground")
    pipeline_json = _pipeline(assessment, plan, temporary, preparation_bounds)
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
        "source_units_basis": assessment.coordinate_units.unit_basis,
        "source_units_authoritative": assessment.coordinate_units.authoritative,
        "georeferenced": bool(assessment.crs),
        "processing_coordinate_mode": "georeferenced" if assessment.crs else "source_local",
        "classification_assessment": classification.to_dict() if classification else None,
        "ground_method": "normalized_z_validation" if plan.height_mode is HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z else "automatic_smrf" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "existing_class_2",
        "hag_method": "validated_normalized_z" if plan.height_mode is HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z else "generated_ground_then_delaunay" if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY else "delaunay" if plan.height_mode is HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND else "dtm",
        "dtm": str(assessment.dtm_path or ""),
        "parameters": {"canonical_metres": {"smrf_cell": 1.0, "smrf_threshold": 0.5, "smrf_window": 18.0}, "source_unit_factor": assessment.coordinate_units.from_meters(1.0), "unit_sensitive": ["SMRF cell", "SMRF threshold", "SMRF window", "ground/HAG interpolation distances", "buffers"]},
        "output_dimensions": [*assessment.dimensions.names, "HeightAboveGround"],
        "warnings": list(plan.warnings),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preparation_signature": plan.signature,
        "preparation_support_extent": preparation_bounds,
        "normalized_z_quality": normalized_quality,
        "recommendations": asdict(recommendations),
    }
    _write_json(provenance_path, provenance)
    _write_json(artifact.with_suffix(".checkpoint.json"), {"signature": plan.signature, "provenance": str(provenance_path), "complete": True})
    return PreparedSourceResult(_prepared_request(request, artifact), plan, provenance_path, False, quality=normalized_quality)


def _pipeline(assessment, plan, output, bounds=None):
    source = str(assessment.source)
    reader = "readers.ept" if source.lower().endswith("ept.json") else "readers.copc" if source.lower().endswith((".copc", ".copc.laz")) else "readers.las"
    stages = [{"type": reader, "filename": source}]
    if bounds is not None and reader in {"readers.ept", "readers.copc"}:
        stages[0]["bounds"] = _pdal_bounds(bounds)
    elif bounds is not None:
        stages.append({"type": "filters.crop", "bounds": _pdal_bounds(bounds)})
    if plan.height_mode is HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z:
        stages.append({"type": "filters.ferry", "dimensions": "Z=>HeightAboveGround"})
    if plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY:
        scale = assessment.coordinate_units.from_meters(1.0)
        stages.append({"type": "filters.smrf", "ignore": "Classification[7:7]", "cell": 1.0 * scale, "scalar": 1.25, "slope": 0.15, "threshold": 0.5 * scale, "window": 18.0 * scale, "returns": "last,only"})
    if plan.height_mode is HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z:
        pass
    elif plan.height_mode is HeightNormalizationPlanMode.DTM_EXISTING:
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
    return {"source": str(value.source), "source_fingerprint": value.source_fingerprint, "spatial_reference_mode": value.spatial_reference_mode, "crs": value.crs, "coordinate_units": asdict(value.coordinate_units), "dimensions": value.dimensions.to_dict(), "classification": value.classification.to_dict() if value.classification else None, "dtm_path": str(value.dtm_path or ""), "requested_products": list(value.requested_products), "point_count": value.point_count, "normalized_z_validated": value.normalized_z_validated}


def _plan_dict(value):
    return {"readiness": value.readiness.value, "recovery": value.recovery.value, "height_mode": value.height_mode.value, "steps": [asdict(step) for step in value.steps], "warnings": list(value.warnings), "blockers": list(value.blockers), "signature": value.signature, "prepared_artifact": str(value.prepared_artifact or ""), "large_source": value.large_source}


def prepare_durable_source(spec, request, *, status_root: Path, preparation_bounds=None, normalized_z_candidate=False, runtime_contract=None, progress=None) -> PreparedSourceResult | None:
    """Prepare one source once, before any tiled product worker is allowed to run."""
    status_root = Path(status_root)
    status_root.mkdir(parents=True, exist_ok=True)
    status_path = status_root / "status.json"
    lock_path = status_root / "preparation.lock"
    lock_fd = _acquire_preparation_lock(lock_path)
    os.write(lock_fd, json.dumps({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}).encode("utf-8"))
    started = datetime.now(timezone.utc).isoformat()
    source_path = Path(request.input_path)

    def update(state, message, **extra):
        payload = {
            "state": state,
            "message": message,
            "source_id": hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:12],
            "source_path": str(source_path),
            "source_fingerprint": _source_fingerprint(source_path),
            "source_point_count": getattr(request, "source_point_count", None),
            "requested_products": list(getattr(spec, "requested_products", (str(spec.product),))),
            "effective_crs": getattr(request, "crs", None),
            "effective_units": getattr(request, "source_coordinate_units", ""),
            "preparation_support_extent": preparation_bounds,
            "runtime_contract": dict(runtime_contract or {}),
            "started_at": started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        _write_json(status_path, payload)
        _notify(progress, message)

    try:
        update("ASSESSING", "Assessing Source")
        update("PREPARING", "Preparing Heights")
        result = prepare_request_source(
            spec,
            request,
            progress=lambda message: update("PREPARING", message),
            preparation_bounds=preparation_bounds,
            normalized_z_candidate=normalized_z_candidate,
            runtime_contract=runtime_contract,
        )
        if result is None:
            update("COMPLETE", "Preparation Complete", chosen_hag_method="existing_hag", preparation_artifact_path=str(source_path), reused=True, finished_at=datetime.now(timezone.utc).isoformat())
            return None
        artifact = Path(result.request.input_path)
        update("VALIDATING", "Validating Preparation", preparation_artifact_path=str(artifact), preparation_signature=result.plan.signature)
        if not artifact.is_file():
            raise RuntimeError("SOURCE_PREPARATION_ARTIFACT_MISSING: prepared source was not created.")
        quality = _inspect_prepared_hag(artifact)
        if not quality["valid"]:
            raise RuntimeError("SOURCE_PREPARATION_QUALITY_FAILED: " + "; ".join(quality["warnings"]))
        checksum = _file_checksum(artifact)
        update(
            "COMPLETE",
            "Preparation Complete",
            chosen_hag_method=result.plan.height_mode.value,
            ground_strategy="normalized_z_validation" if result.plan.height_mode is HeightNormalizationPlanMode.EXISTING_NORMALIZED_Z else "existing_or_automatic_ground",
            preparation_artifact_path=str(artifact),
            artifact_checksum=checksum,
            quality_metrics=quality,
            preparation_signature=result.plan.signature,
            reused=result.reused,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        return replace(result, status_path=status_path, quality=quality)
    except Exception as exc:
        update("FAILED", "PyForestScan could not prepare normalized tree heights for this LiDAR source.", error_code=_preparation_error_code(exc), technical_message=str(exc), finished_at=datetime.now(timezone.utc).isoformat())
        raise
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def _scope_plan(plan, checkpoint_root: Path, bounds, runtime_contract=None):
    if plan.prepared_artifact is None:
        return plan
    payload = json.dumps({"base_signature": plan.signature, "support_extent": bounds, "runtime_contract": dict(runtime_contract or {})}, sort_keys=True, default=str)
    signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return replace(plan, signature=signature, prepared_artifact=checkpoint_root / signature / "prepared_hag.laz")


def _inspect_normalized_z(source: Path, bounds) -> dict[str, object]:
    """Validate a normalized-Z candidate using bounded point evidence, never its filename."""
    try:
        import numpy
        import pdal
        stages = [{"type": "readers.las", "filename": str(source)}]
        if bounds is not None:
            stages.append({"type": "filters.crop", "bounds": _pdal_bounds(bounds)})
        stages.extend(({"type": "filters.decimation", "step": 251}, {"type": "filters.head", "count": 50000}))
        pipeline = pdal.Pipeline(json.dumps({"pipeline": stages}))
        pipeline.execute()
        arrays = tuple(pipeline.arrays)
        if not arrays:
            return {"valid": False, "warnings": ["Normalized-Z inspection returned no points."]}
        array = arrays[0] if len(arrays) == 1 else numpy.concatenate(arrays)
        names = tuple(array.dtype.names or ())
        if "Z" not in names:
            return {"valid": False, "warnings": ["Normalized-Z inspection found no Z dimension."]}
        existing_hag = "HeightAboveGround" in names or "HeightAboveGroundNormalized" in names
        values = numpy.asarray(array["Z"], dtype=float)
        finite = values[numpy.isfinite(values)]
        if not len(finite):
            return {"valid": False, "warnings": ["Normalized-Z inspection found no finite Z values."]}
        q01, median, q99 = (float(item) for item in numpy.quantile(finite, (0.01, 0.5, 0.99)))
        negative_fraction = float(numpy.count_nonzero(finite < 0) / len(finite))
        near_ground_fraction = float(numpy.count_nonzero(numpy.abs(finite) <= 1.0) / len(finite))
        ground_median = None
        if "Classification" in names:
            ground = values[numpy.asarray(array["Classification"]) == 2]
            ground = ground[numpy.isfinite(ground)]
            if len(ground):
                ground_median = float(numpy.median(ground))
        valid = len(finite) >= 100 and q01 >= -10.0 and q99 <= 150.0 and q99 - q01 >= 2.0 and negative_fraction <= 0.25 and near_ground_fraction >= 0.001 and (ground_median is None or abs(ground_median) <= 1.5)
        warnings = [] if valid else ["Z did not satisfy finite/range/near-ground/class-2 normalized-height criteria."]
        return {"valid": valid and not existing_hag, "existing_hag": existing_hag, "observed_dimensions": list(names), "sample_count": len(values), "finite_fraction": len(finite) / len(values), "q01": q01, "median": median, "q99": q99, "minimum": float(numpy.min(finite)), "maximum": float(numpy.max(finite)), "negative_fraction": negative_fraction, "near_ground_fraction": near_ground_fraction, "ground_median": ground_median, "warnings": [] if existing_hag else warnings}
    except Exception as exc:
        return {"valid": False, "warnings": [f"Normalized-Z validation could not complete: {exc}"]}


def _inspect_prepared_hag(path: Path) -> dict[str, object]:
    try:
        import numpy
        import pdal
        pipeline = pdal.Pipeline(json.dumps({"pipeline": [{"type": "readers.las", "filename": str(path)}, {"type": "filters.decimation", "step": 251}, {"type": "filters.head", "count": 50000}]}))
        pipeline.execute()
        arrays = tuple(pipeline.arrays)
        array = arrays[0] if len(arrays) == 1 else numpy.concatenate(arrays)
        names = tuple(array.dtype.names or ())
        if "HeightAboveGround" not in names:
            return {"valid": False, "warnings": ["HeightAboveGround dimension is missing from prepared source."]}
        values = numpy.asarray(array["HeightAboveGround"], dtype=float)
        finite = values[numpy.isfinite(values)]
        valid = bool(len(finite) and len(finite) / max(1, len(values)) >= 0.95 and float(numpy.max(finite) - numpy.min(finite)) > 1e-9)
        return {"valid": valid, "sample_count": len(values), "finite_fraction": len(finite) / max(1, len(values)), "minimum": None if not len(finite) else float(numpy.min(finite)), "maximum": None if not len(finite) else float(numpy.max(finite)), "warnings": [] if valid else ["Prepared HeightAboveGround values failed finite/range validation."]}
    except Exception as exc:
        return {"valid": False, "warnings": [f"PREPARED_SOURCE_READ_FAILED: {exc}"]}


def _pdal_bounds(bounds) -> str:
    if isinstance(bounds, dict):
        xmin, ymin, xmax, ymax = (float(bounds[key]) for key in ("xmin", "ymin", "xmax", "ymax"))
    else:
        xmin, ymin, xmax, ymax = (float(getattr(bounds, key)) for key in ("xmin", "ymin", "xmax", "ymax"))
    return f"([{xmin},{xmax}],[{ymin},{ymax}])"


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preparation_error_code(exc: Exception) -> str:
    text = str(exc)
    for code in ("SOURCE_PREPARATION_QUALITY_FAILED", "SOURCE_PREPARATION_ARTIFACT_MISSING", "SOURCE_PREPARATION_SIGNATURE_MISMATCH", "NORMALIZED_Z_VALIDATION_FAILED", "PREPARED_SOURCE_READ_FAILED"):
        if code in text:
            return code
    if "PREPARATION_VALIDATION_FAILED" in text:
        return "SOURCE_PREPARATION_QUALITY_FAILED"
    return "SOURCE_PREPARATION_FAILED"


def _acquire_preparation_lock(path: Path) -> int:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            owner = int(payload.get("pid", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            owner = 0
        if owner and _pid_running(owner):
            raise RuntimeError(f"SOURCE_PREPARATION_FAILED: coordinator process {owner} owns this source preparation lock.")
        try:
            path.unlink()
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError as exc:
            raise RuntimeError("SOURCE_PREPARATION_FAILED: stale source preparation lock could not be recovered.") from exc


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


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
