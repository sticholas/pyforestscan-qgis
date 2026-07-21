"""Fast PBM request validation before opening point-cloud data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pyforestscan_qgis.backend_runner.api_contract import inspect_api_contract
from pyforestscan_qgis.core.ept_bounds import EptBounds, EptBoundsError, validate_pdal_bounds_expression, validate_pyforestscan_bounds_value
from pyforestscan_qgis.core.job_diagnostics import create_diagnostics_dir, write_environment_diagnostics, write_json, write_text


@dataclass(frozen=True)
class RequestValidationResult:
    passed: bool
    checks: tuple[dict[str, Any], ...]
    diagnostics_dir: Path
    normalized_bounds: dict[str, Any] | None = None
    pdal_bounds_expression: str = ""

    def failed_checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(check for check in self.checks if check.get("status") != "passed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": list(self.checks),
            "diagnostics_dir": str(self.diagnostics_dir),
            "normalized_bounds": self.normalized_bounds,
            "pdal_bounds_expression": self.pdal_bounds_expression,
        }


class RequestValidationError(RuntimeError):
    def __init__(self, result: RequestValidationResult) -> None:
        self.result = result
        failures = "; ".join(str(check.get("message") or check.get("name")) for check in result.failed_checks())
        super().__init__(failures or "Processing request validation failed.")


def validate_processing_request(spec: Any, request: Any, *, api_contract_provider: Callable[[], dict[str, Any]] | None = None) -> RequestValidationResult:
    diagnostics_dir = create_diagnostics_dir(spec.run_folder)
    checks: list[dict[str, Any]] = []
    normalized_bounds: dict[str, Any] | None = None
    expression = ""

    input_path = Path(spec.input_lidar_path)
    _check(checks, "ept_json_exists", input_path.exists(), f"ept.json exists: {input_path}", f"ept.json is missing: {input_path}")
    ept_payload: dict[str, Any] | None = None
    if input_path.exists() and input_path.name.lower() == "ept.json":
        try:
            ept_payload = json.loads(input_path.read_text(encoding="utf-8"))
            _check(checks, "ept_json_parses", True, "ept.json parses as JSON.", "")
        except Exception as exc:  # noqa: BLE001
            _check(checks, "ept_json_parses", False, "", f"ept.json could not be parsed: {exc}")
    elif input_path.exists():
        _check(checks, "input_exists", True, f"Input exists: {input_path}", "")

    ept_crs = _ept_crs(ept_payload) if ept_payload else str(spec.crs or "")
    if input_path.name.lower() == "ept.json":
        _check(checks, "ept_crs_declared", bool(ept_crs), f"EPT CRS detected: {ept_crs}", "EPT CRS is not declared.")

    raw_bounds = getattr(request, "bounds", None)
    if raw_bounds is not None:
        try:
            bounds = EptBounds.from_value(raw_bounds, crs=str(spec.crs or ept_crs), source="polygon_envelope", transformed=True)
            final_value = bounds.to_pyforestscan_value()
            validate_pyforestscan_bounds_value(final_value)
            expression = bounds.to_pdal_range_string()
            grammar = validate_pdal_bounds_expression(expression)
            _check(checks, "ept_bounds_valid", grammar.valid, f"EPT bounds are canonical: {expression}", grammar.reason)
            normalized_bounds = bounds.to_json()
            if ept_payload and "bounds" in ept_payload:
                _check(checks, "ept_bounds_overlap_dataset", _overlaps_ept_bounds(bounds, ept_payload.get("bounds")), "Requested bounds overlap the EPT root extent.", "Requested EPT bounds do not overlap the EPT root extent.")
        except EptBoundsError as exc:
            _check(checks, "ept_bounds_valid", False, "", str(exc))
    else:
        _check(checks, "ept_bounds_optional", True, "No EPT bounds were supplied for this request.", "")

    polygon_path = getattr(request, "crop_polygon_path", None)
    if polygon_path:
        _validate_polygon_path(checks, Path(polygon_path), str(spec.crs or ept_crs))
    for output_path in [Path(path) for path in dict(getattr(spec, "output_paths", {}) or {}).values()]:
        _validate_output_folder(checks, output_path.parent)

    contract = (api_contract_provider or inspect_api_contract)()
    write_json(diagnostics_dir / "backend_contract.json", contract)
    _check(checks, "backend_api_compatible", bool(contract.get("compatible")), "PyForestScan API contract is compatible.", "The managed backend uses a PyForestScan version that is not compatible with this processing request.")
    for key in ("bounds_parameter_present", "crop_poly_parameter_present", "poly_parameter_present"):
        _check(checks, f"api_{key}", bool(contract.get(key)), f"read_lidar supports {key}.", f"read_lidar is missing {key}.")

    pyforestscan_arguments = {"bounds_type": None, "nested_range_types": [], "pdal_bounds_expression": expression}
    if raw_bounds is not None and normalized_bounds is not None:
        final_value = EptBounds.from_value(normalized_bounds).to_pyforestscan_value()
        pyforestscan_arguments = {
            "bounds_type": type(final_value).__name__,
            "nested_range_types": [type(item).__name__ for item in final_value],
            "bounds_value": final_value,
            "pdal_bounds_expression": expression,
        }
    passed = all(check.get("status") == "passed" for check in checks)
    result = RequestValidationResult(passed, tuple(checks), diagnostics_dir, normalized_bounds, expression)
    write_json(diagnostics_dir / "request_validation.json", result.to_dict())
    write_json(diagnostics_dir / "normalized_request.json", {"job_id": spec.job_id, "product": spec.product, "input_lidar_path": str(spec.input_lidar_path), "ept_bounds": normalized_bounds, "output_paths": {key: str(value) for key, value in spec.output_paths.items()}})
    write_json(diagnostics_dir / "pyforestscan_arguments.json", pyforestscan_arguments)
    write_environment_diagnostics(diagnostics_dir / "environment.json")
    write_text(diagnostics_dir / "progress_events.jsonl", "")
    if expression:
        write_json(diagnostics_dir / "pdal_pipeline.json", {"pipeline": [{"type": "readers.ept", "filename": str(spec.input_lidar_path), "bounds": expression}]})
    if not passed:
        raise RequestValidationError(result)
    return result


def _check(checks: list[dict[str, Any]], name: str, passed: bool, passed_message: str, failed_message: str) -> None:
    checks.append({"name": name, "status": "passed" if passed else "failed", "message": passed_message if passed else failed_message})


def _ept_crs(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    srs = payload.get("srs")
    if isinstance(srs, dict):
        authority = srs.get("authority") or srs.get("horizontal") or srs.get("wkt")
        if authority:
            return str(authority)
    return str(payload.get("crs") or "")


def _overlaps_ept_bounds(bounds: EptBounds, raw: Any) -> bool:
    try:
        values = list(raw)
        if len(values) >= 5:
            xmin, ymin, xmax, ymax = float(values[0]), float(values[1]), float(values[3]), float(values[4])
        elif len(values) == 4:
            xmin, ymin, xmax, ymax = float(values[0]), float(values[1]), float(values[2]), float(values[3])
        else:
            return True
    except Exception:
        return True
    return not (bounds.xmax <= xmin or bounds.xmin >= xmax or bounds.ymax <= ymin or bounds.ymin >= ymax)


def _validate_polygon_path(checks: list[dict[str, Any]], path: Path, expected_crs: str) -> None:
    _check(checks, "polygon_file_exists", path.exists(), f"Clipping polygon exists: {path}", f"Clipping polygon is missing: {path}")
    if not path.exists():
        return
    if path.suffix.lower() in {".geojson", ".json"}:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            features = payload.get("features", []) if isinstance(payload, dict) else []
            geometry = features[0].get("geometry", {}) if features else {}
            geometry_type = str(geometry.get("type", ""))
            _check(checks, "polygon_geometry_type", geometry_type in {"Polygon", "MultiPolygon"}, f"Polygon geometry type: {geometry_type}", f"Unsupported polygon geometry type: {geometry_type or 'unknown'}")
            crs = ""
            crs_payload = payload.get("crs") if isinstance(payload, dict) else None
            if isinstance(crs_payload, dict):
                crs = str((crs_payload.get("properties") or {}).get("name") or "")
            _check(checks, "polygon_crs_declared", bool(crs), f"Polygon CRS declared: {crs}", "Polygon CRS is not declared.")
            if crs and expected_crs:
                _check(checks, "polygon_crs_matches", crs == expected_crs, "Polygon CRS matches the request CRS.", f"Polygon CRS {crs} does not match request CRS {expected_crs}.")
            _check(checks, "polygon_geometry_valid", bool(features), "Polygon file contains at least one feature.", "Polygon file contains no features.")
        except Exception as exc:  # noqa: BLE001
            _check(checks, "polygon_file_openable", False, "", f"Polygon file could not be opened: {exc}")
    else:
        _check(checks, "polygon_file_openable", True, f"Polygon file exists with supported external format: {path.suffix or 'unknown'}", "")


def _validate_output_folder(checks: list[dict[str, Any]], folder: Path) -> None:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        test_path = folder / ".pyforestscan_write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        _check(checks, "output_folder_writable", True, f"Output folder is writable: {folder}", "")
    except Exception as exc:  # noqa: BLE001
        _check(checks, "output_folder_writable", False, "", f"Output folder is not writable: {exc}")
