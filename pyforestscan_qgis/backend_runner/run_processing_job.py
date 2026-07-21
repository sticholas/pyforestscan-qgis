"""Command-line entrypoint for PBM managed processing jobs."""

from __future__ import annotations

import argparse
import traceback as traceback_module
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .job_result import BackendJobResult
from .job_spec import BackendJobSpec
from pyforestscan_qgis.core.adapter import PyForestScanAdapter
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
    try:
        adapter = PyForestScanAdapter(execution_mode="qgis_python")
        if spec.product == "dataset_inspection":
            result = _run_dataset_inspection(adapter, spec)
            metrics = _json_ready(asdict(result))
            outputs = {}
        else:
            request = _request_from_spec(spec)
            _request_class, method_name = PRODUCT_REQUESTS[spec.product]
            result = getattr(adapter, method_name)(request)
            metrics = _json_ready(asdict(result))
            outputs = {"primary": Path(metrics.get("output_path", spec.output_paths.get("primary", "")))}
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
        return BackendJobResult(
            job_id=spec.job_id,
            product=spec.product,
            status="failed",
            errors=(str(exc),),
            started_at=started,
            finished_at=_utc_now(),
            traceback=traceback_module.format_exc(),
        )


def _run_dataset_inspection(adapter: PyForestScanAdapter, spec: BackendJobSpec):
    params = dict(spec.product_parameters)
    options = InspectionOptions(
        include_classification_summary=bool(params.get("include_classification_summary", True)),
        include_dimensions=bool(params.get("include_dimensions", True)),
        max_points_for_classification_summary=params.get("max_points_for_classification_summary"),
    )
    return adapter.inspect_dataset(spec.input_lidar_path, options=options)


def _request_from_spec(spec: BackendJobSpec) -> Any:
    if spec.product not in PRODUCT_REQUESTS:
        raise ValueError(f"Unsupported PBM backend product: {spec.product}")
    request_class, _method = PRODUCT_REQUESTS[spec.product]
    params = dict(spec.product_parameters)
    params["input_path"] = spec.input_lidar_path
    params["crs"] = spec.crs
    if "primary" in spec.output_paths:
        params["output_path"] = spec.output_paths["primary"]
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
    parser.add_argument("--spec", required=True, type=Path, help="Path to a PBM backend job spec JSON file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = BackendJobSpec.read(args.spec)
    result = run_spec(spec)
    result.write(spec.result_path)
    if result.success:
        print(f"PBM backend job {result.job_id} completed: {result.product}")
        return 0
    print(f"PBM backend job {result.job_id} failed: {'; '.join(result.errors)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
