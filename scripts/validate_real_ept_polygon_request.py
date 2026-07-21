#!/usr/bin/env python3
"""Validate an EPT polygon processing request without running a full product."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyforestscan_qgis.backend_runner.api_contract import inspect_api_contract
from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.backend_runner.request_validation import RequestValidationError, validate_processing_request
from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec
from pyforestscan_qgis.core.ept_bounds import EptBounds
from pyforestscan_qgis.core.polygon_transport import PolygonExecutionInput
from pyforestscan_qgis.core.types import ChmRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbm-python", type=Path, default=Path(sys.executable), help="PBM backend Python executable.")
    parser.add_argument("--ept-json", type=Path, required=True, help="Path to ept.json.")
    parser.add_argument("--polygon-vector", type=Path, help="Existing polygon vector file. Validate-only reads GeoJSON details when possible.")
    parser.add_argument("--polygon-wkt", help="Polygon WKT to materialize for validation.")
    parser.add_argument("--polygon-crs", required=True, help="Polygon/request CRS such as EPSG:6635.")
    parser.add_argument("--bounds", required=True, help="Requested bounds as xmin,xmax,ymin,ymax[,zmin,zmax].")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output/job directory.")
    parser.add_argument("--validate-only", action="store_true", default=True, help="Run only contract and request validation.")
    parser.add_argument("--test-read", action="store_true", help="Placeholder for a bounded spatial read probe. Not automatic.")
    parser.add_argument("--run-chm", action="store_true", help="Run a real CHM after validation. Requires --confirm-run-chm.")
    parser.add_argument("--confirm-run-chm", action="store_true", help="Explicit confirmation for --run-chm.")
    parser.add_argument("--mock-compatible-contract", action="store_true", help="Fixture-only mode for CI without a PBM backend. Do not use as real evidence.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.run_chm and not args.confirm_run_chm:
        print("--run-chm requires --confirm-run-chm.", file=sys.stderr)
        return 2
    bounds = _parse_bounds(args.bounds, args.polygon_crs)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_folder = args.output_dir / "request_validation_job"
    polygon_input = None
    crop_polygon_path = args.polygon_vector
    if args.polygon_wkt:
        polygon_input = PolygonExecutionInput(
            source_kind="script_wkt",
            geometry_wkt=args.polygon_wkt,
            source_crs_authid=args.polygon_crs,
            processing_crs_authid=args.polygon_crs,
            transformed_geometry_wkt=args.polygon_wkt,
            envelope=(bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax),
            area=max(0.0, (bounds.xmax - bounds.xmin) * (bounds.ymax - bounds.ymin)),
            feature_count=1,
            temporary_vector_format="GeoJSON",
        )
    request = ChmRequest(
        input_path=args.ept_json,
        output_path=run_folder / "outputs" / "chm.tif",
        grid_resolution=1.0,
        crs=args.polygon_crs,
        bounds=bounds.to_pyforestscan_value(),
        crop_polygon=args.polygon_wkt,
        crop_polygon_path=crop_polygon_path,
        polygon_execution_input=polygon_input,
    )
    spec = build_job_spec_from_request("chm", request, run_folder=run_folder)
    backend_request = _request_from_spec(spec)
    try:
        result = validate_processing_request(spec, backend_request, api_contract_provider=_fixture_contract if args.mock_compatible_contract else None)
        status = "passed"
    except RequestValidationError as exc:
        result = exc.result
        status = "failed"
    payload = {
        "status": status,
        "pbm_python": str(args.pbm_python),
        "api_contract": _fixture_contract() if args.mock_compatible_contract else _pbm_contract(args.pbm_python),
        "fixture_contract": bool(args.mock_compatible_contract),
        "normalized_ept_bounds": bounds.to_json(),
        "pyforestscan_bounds_value": bounds.to_pyforestscan_value(),
        "python_argument_types": {
            "bounds": type(bounds.to_pyforestscan_value()).__name__,
            "nested_ranges": [type(item).__name__ for item in bounds.to_pyforestscan_value()],
        },
        "derived_pdal_expression": bounds.to_pdal_range_string(),
        "request_validation": result.to_dict(),
        "diagnostic_bundle": str(result.diagnostics_dir),
        "test_spatial_read": "available as explicit troubleshooting mode; not run by validate-only",
    }
    if args.test_read:
        payload["test_spatial_read"] = "not executed by this script yet; reserved for bounded reader probe after user confirmation"
    if args.run_chm and status == "passed":
        payload["run_chm"] = "confirmed, but production CHM execution remains delegated to QGIS/PBM job runner"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _parse_bounds(text: str, crs: str) -> EptBounds:
    parts = [float(item.strip()) for item in text.split(",") if item.strip()]
    if len(parts) == 4:
        return EptBounds(parts[0], parts[1], parts[2], parts[3], crs=crs, source="user_override")
    if len(parts) == 6:
        return EptBounds(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], crs=crs, source="user_override")
    raise ValueError("--bounds must contain four or six comma-separated numeric values.")


def _fixture_contract() -> dict[str, object]:
    return {
        "compatible": True,
        "python_executable": "fixture-python",
        "python_version": "fixture",
        "pyforestscan_version": "fixture",
        "pyforestscan_path": "fixture",
        "read_lidar_signature": "(input_file, crs, hag=True, bounds=None, crop_poly=False, poly=None)",
        "bounds_parameter_present": True,
        "crop_poly_parameter_present": True,
        "poly_parameter_present": True,
        "pdal_version": "fixture",
        "gdal_version": "fixture",
        "plugin_adapter_contract_version": "ept-bounds-v1",
    }


def _pbm_contract(python: Path) -> dict[str, object]:
    if Path(python).resolve() == Path(sys.executable).resolve():
        return inspect_api_contract()
    try:
        completed = subprocess.run([str(python), "-m", "pyforestscan_qgis.backend_runner", "inspect_api_contract"], check=False, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        return json.loads(completed.stdout)
    except Exception as exc:  # noqa: BLE001
        return {"compatible": False, "errors": [str(exc)]}


if __name__ == "__main__":
    raise SystemExit(main())
