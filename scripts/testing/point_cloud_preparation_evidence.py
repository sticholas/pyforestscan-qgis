"""Managed-runtime preparation audit; original files are read-only."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan import filters
    from pyforestscan_qgis.core.classification_inspection import assessment_from_array
    from pyforestscan_qgis.core.lidar_preparation import build_preparation_assessment, HeightNormalizationPlanner
    from pyforestscan_qgis.core.source_coordinate_units import assess_source_coordinate_units
    from pyforestscan_qgis.core.point_cloud.preparation import PreparationOptions
    from pyforestscan_qgis.core.point_cloud.preparation_execution import prepare_arrays
    before = digest(args.source)
    report = {"source": str(args.source), "source_sha256": before,
              "pyforestscan_version": importlib.metadata.version("pyforestscan"),
              "filters_sha256": digest(Path(filters.__file__)),
              "scope": "In-memory filter qualification, not workspace integration or file export",
              "checks": [], "passed": False}
    try:
        pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(args.source)}]))
        info = next(iter(pipeline.quickinfo.values()))
        if info["num_points"] > 250000:
            raise ValueError("This bounded audit fixture must contain at most 250,000 points.")
        pipeline.execute()
        original = pipeline.arrays[0]
        dtype = original.dtype.descr + [("AuditRecordId", "u8")]
        source = np.empty(len(original), dtype=dtype)
        for field in original.dtype.names:
            source[field] = original[field]
        source["AuditRecordId"] = np.arange(len(source))
        baseline = source.copy()
        for name, call in (
            ("poisson_radius_0.5", lambda data: filters.downsample_poisson(data, .5)),
            ("voxel_first_0.5", lambda data: filters.downsample_voxel(data, .5, "first")),
            ("hag_delaunay", lambda data: filters.add_height_above_ground(data, method="delaunay")),
        ):
            started = time.monotonic()
            result = np.concatenate(call([source.copy()]))
            ids = result["AuditRecordId"].astype(np.int64)
            assert len(result) > 0 and len(np.unique(ids)) == len(ids)
            assert np.all((ids >= 0) & (ids < len(source)))
            for field in original.dtype.names:
                if field == "HeightAboveGround" and name == "hag_delaunay":
                    continue
                assert np.array_equal(result[field], source[field][ids]), field
            assert np.array_equal(source, baseline)
            if name == "hag_delaunay":
                assert len(result) == len(source)
                assert np.all(np.isfinite(result["HeightAboveGround"]))
            else:
                assert len(result) < len(source)
            report["checks"].append({"operation": name, "input_points": len(source),
                "output_points": len(result), "seconds": time.monotonic()-started,
                "original_attributes_preserved": True, "input_array_unchanged": True,
                "dimensions": list(result.dtype.names)})
        metadata = pipeline.metadata["metadata"]["readers.las"]
        crs = metadata.get("comp_spatialreference") or metadata.get("spatialreference") or None
        assessment = build_preparation_assessment(
            source=args.source, spatial_reference_mode="resolved" if crs else "source_local",
            crs=crs, coordinate_units=assess_source_coordinate_units(crs),
            dimensions=source.dtype.names, classification=assessment_from_array(source),
            dtm_path=None, requested_products=("chm",), point_count=len(source))
        plan = HeightNormalizationPlanner().plan(assessment)
        report["height_plan"] = {"mode": plan.height_mode.value, "can_execute": plan.can_execute,
                                 "warnings": list(plan.warnings), "blockers": list(plan.blockers)}
        for name, options in (
            ("wrapper_voxel", PreparationOptions(thinning="voxel_first", spacing=.5)),
            ("wrapper_add_hag", PreparationOptions(height_action="add_hag")),
            ("wrapper_normalize_poisson", PreparationOptions(
                thinning="poisson", spacing=.5, height_action="normalize_z")),
        ):
            started = time.monotonic()
            prepared = prepare_arrays((source,), options, filters_module=filters,
                assessment=assessment, plan=plan, run_folder=args.output_dir / name,
                job_identity=name)
            result = np.concatenate(prepared.arrays)
            ids = result["AuditRecordId"].astype(np.int64)
            assert np.all((ids >= 0) & (ids < len(source)))
            assert len(np.unique(ids)) == len(ids)
            for field in original.dtype.names:
                if field == "HeightAboveGround" and options.height_action != "preserve":
                    continue
                output_field = "PFSOriginalZ" if field == "Z" and options.height_action == "normalize_z" else field
                assert np.array_equal(result[output_field], source[field][ids], equal_nan=True), field
            if options.height_action == "normalize_z":
                assert np.array_equal(result["Z"], result["HeightAboveGround"])
            assert "PFSPreparationRecordId" not in result.dtype.names
            assert np.array_equal(source, baseline)
            report["checks"].append({"operation": name, "input_points": len(source),
                "output_points": len(result), "seconds": time.monotonic()-started,
                "original_attributes_preserved": True, "input_array_unchanged": True,
                "height_provenance": prepared.height_provenance,
                "dimensions": list(result.dtype.names)})
        report["source_unchanged"] = digest(args.source) == before
        assert report["source_unchanged"]
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (args.output_dir / "preparation-evidence.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
