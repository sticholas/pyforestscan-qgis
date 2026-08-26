"""Command-line entrypoint for PBM managed processing jobs."""

from __future__ import annotations

import argparse
import traceback as traceback_module
import json
import os
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .job_result import BackendJobResult
from .job_spec import BackendJobSpec
from .job_spec import PBM_PROTOCOL_VERSION
from .runtime_contract import inspect_runtime_contract, print_runtime_contract
from .pbm_lidar_preparation import prepare_request_source
from .api_contract import print_api_contract
from .request_validation import RequestValidationError, validate_processing_request
from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.job_diagnostics import classify_exception, create_diagnostics_dir, support_summary, write_failure_bundle, write_json
from pyforestscan_qgis.core.hag_strategy import HagExecutionDecision, assess_hag_suitability
from pyforestscan_qgis.core.height_normalization import HeightNormalizationDecision, HeightNormalizationMode
from pyforestscan_qgis.core.spatial_reference_contract import SpatialReferenceContract
from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.config import InspectionOptions
from pyforestscan_qgis.core.ept_subset import EptSubsetRequest
from pyforestscan_qgis.core.polygon_transport import materialize_polygon_input
from pyforestscan_qgis.core.types import (
    CanopyCoverRequest,
    ChmRequest,
    DtmRequest,
    FhdRequest,
    PadRequest,
    PaiRequest,
    PointDensityRequest,
    RumpleRequest,
    VoxelStatRequest,
)
from pyforestscan_qgis.core.backend.native_runtime import print_native_runtime
from pyforestscan_qgis.core.backend.processing_engine import ProcessingRuntimeToken, contract_hash

PRODUCT_REQUESTS = {
    "chm": (ChmRequest, "create_chm"),
    "canopy_cover": (CanopyCoverRequest, "create_canopy_cover"),
    "pad": (PadRequest, "create_pad"),
    "pai": (PaiRequest, "create_pai"),
    "fhd": (FhdRequest, "create_fhd"),
    "rumple": (RumpleRequest, "create_rumple"),
    "dtm": (DtmRequest, "generate_dtm"),
    "point_density": (PointDensityRequest, "create_point_density"),
    "voxel_stat": (VoxelStatRequest, "create_voxel_stat"),
    "ept_subset_extract": (EptSubsetRequest, "extract_lidar_subset"),
}


def run_spec(spec: BackendJobSpec) -> BackendJobResult:
    """Run one backend job spec and return a structured result."""
    started = _utc_now()
    stop = threading.Event()
    heartbeat_state = {"stage": "Validating Inputs", "activity": "Validating backend request.", "current_work_unit_id": str(spec.product_parameters.get("work_unit_id", "")), "completed_count": int(spec.product_parameters.get("completed_count", 0)), "total_count": int(spec.product_parameters.get("total_count", 1)), "retry_count": int(spec.product_parameters.get("retry_count", 0))}
    heartbeat_started = time.monotonic()
    heartbeat = threading.Thread(target=_heartbeat_loop, args=(spec, stop, heartbeat_state, heartbeat_started), daemon=True)
    heartbeat.start()
    _write_heartbeat(spec, heartbeat_state, heartbeat_started)
    try:
        _validate_runtime_protocol(spec)
        diagnostics_dir = create_diagnostics_dir(spec.run_folder)
        runtime_contract = inspect_runtime_contract()
        _validate_runtime_token(spec, runtime_contract)
        write_json(diagnostics_dir / "backend_module_locations.json", runtime_contract)
        _write_execution_runtime_trace(spec, runtime_contract)
        _update_source_local_trace(spec, "backend_runner_input", {
            "spatial_reference": spec.spatial_reference,
            "height_normalization": spec.height_normalization,
            "source_dimensions": spec.product_parameters.get("source_dimensions", []),
        })
        adapter = PyForestScanAdapter(execution_mode="qgis_python")
        if spec.product == "dataset_inspection":
            result = _run_dataset_inspection(adapter, spec)
            metrics = _json_ready(asdict(result))
            outputs = {}
        else:
            request = _request_from_spec(spec)
            heartbeat_state.update(stage="Inspecting Ground Returns", activity="Assessing LiDAR preparation requirements.")
            _write_heartbeat(spec, heartbeat_state, heartbeat_started)
            preparation = prepare_request_source(spec, request, progress=lambda message: heartbeat_state.update(stage=message, activity=message))
            if preparation is not None:
                request = preparation.request
                _update_source_local_trace(spec, "preparation", {"mode": preparation.plan.height_mode.value, "signature": preparation.plan.signature, "artifact": str(getattr(request, "input_path", "")), "reused": preparation.reused, "provenance": str(preparation.provenance_path)})
            validation = validate_processing_request(spec, request)
            heartbeat_state.update(stage="Reading LiDAR", activity="Backend adapter is processing the selected bounded source.")
            _write_heartbeat(spec, heartbeat_state, heartbeat_started)
            if spec.product == "chm" and bool(spec.product_parameters.get("inspect_hag_suitability")):
                heartbeat_state.update(stage="Inspecting Ground Support", activity="Checking bounded points before Delaunay height normalization.")
                _write_heartbeat(spec, heartbeat_state, heartbeat_started)
                report = _inspect_bounded_hag_input(spec)
                decision = HagExecutionDecision.from_report(report)
                planned = str(spec.product_parameters.get("hag_method") or decision.selected_method)
                decision.assert_executed(planned)
                request = __import__("dataclasses").replace(request,hag_method=decision.selected_method,hag_source_dimension=decision.source_dimension,hag_method_signature=decision.method_signature,crop_polygon=None,crop_polygon_path=None,polygon_execution_input=None)
                write_json(create_diagnostics_dir(spec.run_folder)/"hag_execution_decision.json",asdict(decision))
            _request_class, method_name = PRODUCT_REQUESTS[spec.product]
            result = getattr(adapter, method_name)(request)
            metrics = _json_ready(asdict(result))
            if preparation is not None:
                metrics["preparation"] = {"mode": preparation.plan.height_mode.value, "signature": preparation.plan.signature, "provenance": str(preparation.provenance_path), "reused": preparation.reused}
                _tag_preparation_output(Path(metrics.get("output_path", "")), preparation)
            outputs = {"primary": Path(metrics.get("output_path", spec.output_paths.get("primary", "")))}
        heartbeat_state.update(stage="Finalizing Output", activity="Product calculation completed.", completed_count=heartbeat_state["total_count"])
        _write_heartbeat(spec, heartbeat_state, heartbeat_started)
        _update_source_local_trace(spec, "terminal", {"status": "success", "outputs": {key: str(value) for key, value in outputs.items()}})
        stop.set()
        return BackendJobResult(
            job_id=spec.job_id,
            product=spec.product,
            status="success",
            outputs=outputs,
            started_at=started,
            finished_at=_utc_now(),
            product_metrics=metrics,
        )
    except Exception as exc:  # noqa: BLE001 - backend runner must serialize failures.
        diagnostics_dir = create_diagnostics_dir(spec.run_folder)
        structured_error = classify_exception(exc, stage="Request Validation" if isinstance(exc, RequestValidationError) else "Processing")
        _update_source_local_trace(spec, "terminal", {"status": "failed", "error_code": structured_error.code, "message": structured_error.user_message})
        write_failure_bundle(diagnostics_dir, job_id=spec.job_id, product=spec.product, error=structured_error)
        try:
            contract = json.loads((diagnostics_dir / "backend_contract.json").read_text(encoding="utf-8")) if (diagnostics_dir / "backend_contract.json").exists() else {}
        except Exception:
            contract = {}
        write_json(
            diagnostics_dir / "support_summary.json",
            {
                "text": support_summary(
                    job_id=spec.job_id,
                    plugin_version=spec.plugin_version,
                    product=spec.product,
                    error=structured_error,
                    backend=contract,
                    diagnostic_bundle=diagnostics_dir,
                )
            },
        )
        stop.set()
        return BackendJobResult(
            job_id=spec.job_id,
            product=spec.product,
            status="failed",
            warnings=(f"Diagnostics written to {diagnostics_dir}",),
            errors=(structured_error.user_message, structured_error.technical_message),
            started_at=started,
            finished_at=_utc_now(),
            traceback=traceback_module.format_exc(),
            error_code=structured_error.code,
            retryable=structured_error.retryable,
        )


def _write_heartbeat(spec: BackendJobSpec, state: dict[str, Any], started: float) -> None:
    path = spec.run_folder / "progress" / "heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"job_id": spec.job_id, "attempt_id": str(spec.product_parameters.get("attempt_id", "attempt-1")), "timestamp": _utc_now(), "process_id": os.getpid(), "current_stage": state["stage"], "current_product": spec.product, "latest_activity": state["activity"], "elapsed_seconds": round(time.monotonic() - started, 3), "current_work_unit_id": state.get("current_work_unit_id", ""), "latest_completed_unit": state.get("latest_completed_unit", ""), "completed_count": state.get("completed_count", 0), "total_count": state.get("total_count", 1), "retry_count": state.get("retry_count", 0), "points_processed": state.get("points_processed"), "bytes_processed": state.get("bytes_processed"), "process_alive": True}
    atomic_write_json(path,payload)

def _heartbeat_loop(spec: BackendJobSpec, stop: threading.Event, state: dict[str, Any], started: float) -> None:
    while not stop.wait(15):
        _write_heartbeat(spec, state, started)

def _run_dataset_inspection(adapter: PyForestScanAdapter, spec: BackendJobSpec):
    params = dict(spec.product_parameters)
    options = InspectionOptions(
        include_classification_summary=bool(params.get("include_classification_summary", True)),
        include_dimensions=bool(params.get("include_dimensions", True)),
        max_points_for_classification_summary=params.get("max_points_for_classification_summary"),
    )
    return adapter.inspect_dataset(spec.input_lidar_path, options=options)

def _inspect_bounded_hag_input(spec: BackendJobSpec):
    """Read one bounded EPT window without HAG and reject unsafe geometry."""
    import pdal
    bounds=str(spec.product_parameters.get("pdal_bounds_expression") or "")
    if not bounds:raise RuntimeError("HAG invalid work-unit geometry: bounded EPT expression is missing.")
    pipeline=pdal.Pipeline(json.dumps({"pipeline":[{"type":"readers.ept","filename":str(spec.input_lidar_path),"bounds":bounds}]}));pipeline.execute();arrays=tuple(pipeline.arrays or ())
    if not arrays:
        report=assess_hag_suitability((),(),work_unit_id=str(spec.product_parameters.get("work_unit_id","")))
    else:
        array=arrays[0] if len(arrays)==1 else __import__('numpy').concatenate(arrays);names=set(array.dtype.names or ());report=assess_hag_suitability(array['X'] if 'X' in names else (),array['Y'] if 'Y' in names else (),array['Classification'] if 'Classification' in names else (),dimensions=names,z=array['Z'] if 'Z' in names else (),hag_values=array['HeightAboveGround'] if 'HeightAboveGround' in names else (),work_unit_id=str(spec.product_parameters.get("work_unit_id","")))
    write_json(create_diagnostics_dir(spec.run_folder)/"hag_suitability.json",report.to_dict())
    if not report.suitable:raise RuntimeError(f"{report.reason_code}: {report.user_message} ({report.technical_message})")
    return report


def _request_from_spec(spec: BackendJobSpec) -> Any:
    if spec.product not in PRODUCT_REQUESTS:
        raise ValueError(f"Unsupported PBM backend product: {spec.product}")
    request_class, _method = PRODUCT_REQUESTS[spec.product]
    params = dict(spec.product_parameters)
    params["input_path"] = spec.input_lidar_path
    spatial = SpatialReferenceContract.from_dict(spec.spatial_reference)
    params["crs"] = spatial.crs
    if "hag_method" in request_class.__dataclass_fields__:
        decision = HeightNormalizationDecision.from_dict(spec.height_normalization)
        params["hag_method"] = decision.adapter_method
        params["hag_source_dimension"] = decision.source_dimension or "HeightAboveGround"
        params["hag_method_signature"] = decision.method_signature
    if "primary" in spec.output_paths:
        params["output_path"] = spec.output_paths["primary"]
    if params.get("ept_bounds") and "bounds" in request_class.__dataclass_fields__:
        params["bounds"] = params["ept_bounds"]
    if spec.dtm_path is not None and "dtm_path" in request_class.__dataclass_fields__:
        params["dtm_path"] = spec.dtm_path
    if params.get("polygon_execution_input") and "crop_polygon_path" in request_class.__dataclass_fields__:
        prepared = materialize_polygon_input(params["polygon_execution_input"], spec.run_folder)
        params["crop_polygon_path"] = prepared.temporary_vector_path
        params["polygon_vector_format"] = prepared.temporary_vector_format
    field_names = set(request_class.__dataclass_fields__)
    clean = {key: _coerce_value(key, value) for key, value in params.items() if key in field_names}
    return request_class(**clean)


def _coerce_value(key: str, value: Any) -> Any:
    if key.endswith("path") or key in {"input_path", "output_path", "dtm_path"}:
        return Path(value) if value is not None else None
    if key in {"bounds", "z_index_range"} and isinstance(value, list):
        return tuple(tuple(item) if isinstance(item, list) else item for item in value)
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("inspect_api_contract","inspect_native_runtime","inspect_runtime_contract"), help="Run a PBM-side diagnostic command and exit.")
    parser.add_argument("--spec", type=Path, help="Path to a PBM backend job spec JSON file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inspect_api_contract":
        print_api_contract()
        return 0
    if args.command == "inspect_native_runtime":
        return print_native_runtime()
    if args.command == "inspect_runtime_contract":
        return print_runtime_contract()
    if args.spec is None:
        raise SystemExit("--spec is required unless a diagnostic command is supplied.")
    spec = BackendJobSpec.read(args.spec)
    result = run_spec(spec)
    result.write(spec.result_path)
    if result.success:
        print(f"PBM backend job {result.job_id} completed: {result.product}")
        return 0
    print(f"PBM backend job {result.job_id} failed: {'; '.join(result.errors)}")
    return 1


def _validate_runtime_protocol(spec: BackendJobSpec) -> None:
    if spec.protocol_version != PBM_PROTOCOL_VERSION:
        raise RuntimeError(
            f"BACKEND_CONTRACT_MISMATCH: processing backend needs an update; "
            f"request protocol {spec.protocol_version}, backend protocol {PBM_PROTOCOL_VERSION}. Repair Backend."
        )
    spatial = SpatialReferenceContract.from_dict(spec.spatial_reference)
    if spatial.source_local and spatial.crs is not None:
        raise RuntimeError("BACKEND_CONTRACT_MISMATCH: source-local requests cannot carry a named CRS.")
    decision = HeightNormalizationDecision.from_dict(spec.height_normalization)
    if spec.product in {"chm", "rumple"} and decision.mode is HeightNormalizationMode.UNAVAILABLE:
        raise RuntimeError("BACKEND_CONTRACT_MISMATCH: CHM/Rumple request has no height-normalization decision.")


def _validate_runtime_token(spec: BackendJobSpec, runtime_contract: dict[str, Any]) -> None:
    token = ProcessingRuntimeToken.from_dict(spec.runtime_token)
    if token is None:
        if os.environ.get("PYFORESTSCAN_MANAGED_ENGINE") != "1":
            return
        raise RuntimeError("ENGINE_RUNTIME_TOKEN_MISSING: Processing Engine request must be revalidated before launch.")
    actual_executable = str(Path(runtime_contract.get("python_executable", "")).resolve())
    expected_executable = str(Path(token.executable).resolve())
    if actual_executable != expected_executable:
        raise RuntimeError(f"ENGINE_RUNTIME_CHANGED: expected {expected_executable}, running {actual_executable}.")
    if token.protocol != str(runtime_contract.get("protocol_version", "")):
        raise RuntimeError("ENGINE_PROTOCOL_MISMATCH: Processing Engine protocol changed after verification.")
    if token.contract_hash != contract_hash(runtime_contract):
        raise RuntimeError("ENGINE_RUNTIME_CHANGED: Processing Engine contract changed after verification.")


def _write_execution_runtime_trace(spec: BackendJobSpec, contract: dict[str, Any]) -> None:
    path = create_diagnostics_dir(spec.run_folder) / "execution_runtime_trace.json"
    try:
        trace = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"stages": {}}
    except (OSError, ValueError):
        trace = {"stages": {}}
    trace.setdefault("stages", {})["backend_runner"] = {
        "job_id": spec.job_id, "pid": os.getpid(), "parent_pid": os.getppid(),
        "executable": contract.get("python_executable"), "sys_prefix": os.sys.prefix,
        "cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH", ""),
        "path": os.environ.get("PATH", ""), "sys_path": contract.get("sys_path", []),
        "module_locations": contract.get("module_locations", {}),
        "protocol": contract.get("protocol_version"), "contract_hash": contract_hash(contract),
    }
    atomic_write_json(path, trace)


def _update_source_local_trace(spec: BackendJobSpec, stage: str, payload: dict[str, Any]) -> None:
    try:
        spatial = SpatialReferenceContract.from_dict(spec.spatial_reference)
    except (TypeError, ValueError):
        return
    if not spatial.source_local:
        return
    path = create_diagnostics_dir(spec.run_folder) / "source_local_trace.json"
    try:
        trace = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"job_id": spec.job_id, "product": spec.product, "stages": {}}
    except (OSError, json.JSONDecodeError):
        trace = {"job_id": spec.job_id, "product": spec.product, "stages": {}}
    trace.setdefault("stages", {})[stage] = payload
    write_json(path, trace)


def _tag_preparation_output(path: Path, preparation: object) -> None:
    if not path.is_file() or path.suffix.lower() not in {".tif", ".tiff"}:
        return
    mode = preparation.plan.height_mode.value
    hag_source = {"DELAUNAY_FROM_EXISTING_GROUND": "delaunay", "DTM_EXISTING": "dtm", "AUTO_CLASSIFY_GROUND_THEN_DELAUNAY": "generated_ground_then_delaunay"}.get(mode, "existing")
    try:
        import rasterio
        with rasterio.open(path, "r+") as dataset:
            dataset.update_tags(HAG_SOURCE=hag_source, GROUND_CLASS_SOURCE="automatic_smrf" if mode == "AUTO_CLASSIFY_GROUND_THEN_DELAUNAY" else "existing", PREPARATION_APPLIED="true", PREPARATION_SIGNATURE=preparation.plan.signature, PREPARATION_PROVENANCE=str(preparation.provenance_path))
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit(main())
