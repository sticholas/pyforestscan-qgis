"""Structured processing diagnostics and support summaries."""

from __future__ import annotations

import json
import os
import platform
import traceback as traceback_module
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class JobErrorCode(str, Enum):
    REQUEST_VALIDATION_FAILED = "REQUEST_VALIDATION_FAILED"
    BACKEND_CONTRACT_MISMATCH = "BACKEND_CONTRACT_MISMATCH"
    EPT_BOUNDS_INVALID = "EPT_BOUNDS_INVALID"
    EPT_BOUNDS_OUTSIDE_DATASET = "EPT_BOUNDS_OUTSIDE_DATASET"
    EPT_READER_REJECTED_BOUNDS = "EPT_READER_REJECTED_BOUNDS"
    POLYGON_FILE_INVALID = "POLYGON_FILE_INVALID"
    POLYGON_CRS_UNKNOWN = "POLYGON_CRS_UNKNOWN"
    CRS_TRANSFORM_FAILED = "CRS_TRANSFORM_FAILED"
    OUTPUT_NOT_WRITABLE = "OUTPUT_NOT_WRITABLE"
    PYFORESTSCAN_IMPORT_FAILED = "PYFORESTSCAN_IMPORT_FAILED"
    PYFORESTSCAN_EXECUTION_FAILED = "PYFORESTSCAN_EXECUTION_FAILED"
    PDAL_PIPELINE_FAILED = "PDAL_PIPELINE_FAILED"
    PRODUCT_CALCULATION_FAILED = "PRODUCT_CALCULATION_FAILED"
    OUTPUT_WRITE_FAILED = "OUTPUT_WRITE_FAILED"
    OUTPUT_MASK_FAILED = "OUTPUT_MASK_FAILED"
    HAG_COLLINEAR_INPUT = "HAG_COLLINEAR_INPUT"
    EMPTY_SPATIAL_READ = "EMPTY_SPATIAL_READ"
    HAG_INSUFFICIENT_GROUND = "HAG_INSUFFICIENT_GROUND"
    HAG_INVALID_GEOMETRY = "HAG_INVALID_GEOMETRY"
    NATIVE_BACKEND_CRASH = "NATIVE_BACKEND_CRASH"
    JOB_CANCELLED = "JOB_CANCELLED"
    UNKNOWN_BACKEND_FAILURE = "UNKNOWN_BACKEND_FAILURE"
    SOURCE_DIMENSION_MISMATCH = "SOURCE_DIMENSION_MISMATCH"


@dataclass(frozen=True)
class StructuredJobError:
    code: str
    user_message: str
    technical_message: str
    stage: str
    exception_type: str = ""
    traceback: str = ""
    likely_causes: tuple[str, ...] = ()
    suggested_actions: tuple[str, ...] = ()
    retryable: bool = False
    related_paths: tuple[str, ...] = ()
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    backend_versions: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    job_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProgressEvent:
    job_id: str
    event_sequence: int
    timestamp: str
    stage: str
    status: str
    message: str
    progress_kind: str = "stage"
    progress_value: float | None = None
    diagnostic_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_diagnostics_dir(run_folder: Path | str) -> Path:
    path = Path(run_folder) / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_environment_diagnostics(path: Path) -> Path:
    allowed = {
        "PATH",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "SystemRoot",
        "COMSPEC",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "PYTHONNOUSERSITE",
    }
    env = {key: _redact(value) for key, value in os.environ.items() if key in allowed}
    return write_json(path, {"python_executable": os.sys.executable, "python_version": os.sys.version, "platform": platform.platform(), "environment": env})


def classify_exception(exc: BaseException, *, stage: str = "Processing") -> StructuredJobError:
    text = str(exc)
    lowered = text.lower()
    traceback_text = traceback_module.format_exc()
    if "source_dimension_mismatch" in lowered:
        return StructuredJobError(
            code=JobErrorCode.SOURCE_DIMENSION_MISMATCH.value,
            user_message="The backend did not detect the expected normalized-height field.",
            technical_message=text,
            stage="Reading LiDAR",
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            likely_causes=("Dataset inspection and the PBM execution read reported different point dimensions.",),
            suggested_actions=("Open the source-local trace.", "Re-run Dataset Explorer and retry."),
            retryable=False,
        )
    if "all points collinear" in lowered or "all_points_collinear" in lowered or "ground_points_collinear" in lowered or ("ground" in lowered and "collinear" in lowered):
        return StructuredJobError(code=JobErrorCode.HAG_COLLINEAR_INPUT.value,user_message="Ground-normalization points cannot form a two-dimensional surface in this area.",technical_message=text,stage="Height Normalization",exception_type=type(exc).__name__,traceback=traceback_text,likely_causes=("The bounded ground-point subset is rank-deficient or spatially degenerate.",),suggested_actions=("Inspect Ground Classification.","View Work Unit Statistics."),retryable=False)
    if "empty point" in lowered or "empty_point_array" in lowered or "no point data" in lowered or "no points were returned" in lowered:
        return StructuredJobError(code=JobErrorCode.EMPTY_SPATIAL_READ.value,user_message="No usable LiDAR points were returned for this processing area.",technical_message=text,stage="Reading LiDAR",exception_type=type(exc).__name__,traceback=traceback_text,likely_causes=("The bounded request does not overlap populated EPT data.",),suggested_actions=("Review the affected work-unit extent.","Verify source coverage."),retryable=False)
    if "ground" in lowered and ("too few" in lowered or "insufficient" in lowered):
        return StructuredJobError(code=JobErrorCode.HAG_INSUFFICIENT_GROUND.value,user_message="There are not enough usable ground points for height normalization.",technical_message=text,stage="Height Normalization",exception_type=type(exc).__name__,traceback=traceback_text,suggested_actions=("Inspect Ground Classification.","View Work Unit Statistics."),retryable=False)
    if "No opening '[' in range" in text:
        return StructuredJobError(
            code=JobErrorCode.EPT_READER_REJECTED_BOUNDS.value,
            user_message="The EPT reader rejected the requested spatial bounds.",
            technical_message=text,
            stage=stage,
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            likely_causes=("The coordinate ranges were serialized with parentheses instead of square brackets.",),
            suggested_actions=("Validate the processing request again.", "Repair the backend if validation reports an API mismatch."),
            retryable=True,
        )
    if "bounds" in text.lower():
        return StructuredJobError(
            code=JobErrorCode.EPT_BOUNDS_INVALID.value,
            user_message="The requested EPT bounds are invalid.",
            technical_message=text,
            stage=stage,
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            likely_causes=("The request contained malformed or non-overlapping bounds.",),
            suggested_actions=("Validate the processing request.", "Review polygon CRS and requested extent."),
            retryable=True,
        )
    return StructuredJobError(
        code=JobErrorCode.UNKNOWN_BACKEND_FAILURE.value,
        user_message="The backend job failed before completion.",
        technical_message=text,
        stage=stage,
        exception_type=type(exc).__name__,
        traceback=traceback_text,
        suggested_actions=("View the diagnostic bundle.", "Run Environment Check."),
        retryable=True,
    )


def write_failure_bundle(diagnostics_dir: Path, *, job_id: str, product: str, error: StructuredJobError, stdout: str = "", stderr: str = "") -> None:
    write_json(diagnostics_dir / "summary.json", {"job_id": job_id, "product": product, "status": "failed", "error": error.to_dict()})
    write_text(diagnostics_dir / "traceback.txt", error.traceback or "")
    write_text(diagnostics_dir / "stdout.log", stdout or "")
    write_text(diagnostics_dir / "stderr.log", stderr or "")
    write_json(diagnostics_dir / "checksums.json", {"diagnostic_schema": "phase27l-v1"})
    write_text(diagnostics_dir / "README.txt", "PyForestScan job diagnostics. This bundle intentionally omits credentials and full environment dumps.\n")


def support_summary(
    *,
    job_id: str,
    plugin_version: str,
    product: str,
    error: StructuredJobError,
    bounds_expression: str = "",
    backend: dict[str, Any] | None = None,
    diagnostic_bundle: Path | str | None = None,
) -> str:
    backend = backend or {}
    lines = [
        "PyForestScan QGIS Polygon Job Failure",
        "",
        f"Job ID: {job_id}",
        f"Plugin version: {plugin_version}",
        f"Product: {product}",
        f"Failed stage: {error.stage}",
        f"Error code: {error.code}",
        f"User message: {error.user_message}",
        f"Technical message: {error.technical_message}",
    ]
    if bounds_expression:
        lines.append(f"Derived expression: {bounds_expression}")
    if backend:
        lines.append(f"Backend: python={backend.get('python_executable', 'unknown')}; pyforestscan={backend.get('pyforestscan_version', 'unknown')}; pdal={backend.get('pdal_version', 'unknown')}; gdal={backend.get('gdal_version', 'unknown')}")
    if diagnostic_bundle:
        lines.append(f"Diagnostic bundle: {diagnostic_bundle}")
    return "\n".join(lines) + "\n"


def sanitized_export_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _json_ready({key: _redact(value) for key, value in payload.items()})


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in ("password", "secret", "token", "apikey", "api_key")):
            return "<redacted>"
    return value


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return _json_ready(value.to_dict())
    return value
