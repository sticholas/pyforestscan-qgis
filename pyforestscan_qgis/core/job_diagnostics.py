"""Structured processing diagnostics and support summaries."""

from __future__ import annotations

import json
import os
import platform
import traceback as traceback_module
from html import escape
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .batch import BatchResult


class JobErrorCode(str, Enum):
    ENGINE_DEPENDENCY_MISSING = "ENGINE_DEPENDENCY_MISSING"
    ENGINE_RUNTIME_CHANGED = "ENGINE_RUNTIME_CHANGED"
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
    PRODUCT_EXECUTION_FAILED = "PRODUCT_EXECUTION_FAILED"
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
    NO_HAG_AVAILABLE = "NO_HAG_AVAILABLE"
    GROUND_CLASS_UNAVAILABLE = "GROUND_CLASS_UNAVAILABLE"
    GROUND_CLASSIFICATION_FAILED = "GROUND_CLASSIFICATION_FAILED"
    HAG_GENERATION_FAILED = "HAG_GENERATION_FAILED"
    DTM_GENERATION_FAILED = "DTM_GENERATION_FAILED"
    DTM_INCOMPATIBLE = "DTM_INCOMPATIBLE"
    PREPARATION_VALIDATION_FAILED = "PREPARATION_VALIDATION_FAILED"
    SOURCE_UNITS_UNKNOWN = "SOURCE_UNITS_UNKNOWN"


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
    preparation_codes = {
        "source_units_unknown": (JobErrorCode.SOURCE_UNITS_UNKNOWN.value, "PyForestScan found usable ground data and can prepare this LiDAR. Choose the coordinate units to continue.", ("Choose trusted source units or assign the source coordinate system.",)),
        "ground_class_unavailable": (JobErrorCode.GROUND_CLASS_UNAVAILABLE.value, "PyForestScan could not identify a supported ground-preparation path.", ("Provide a compatible DTM or review ground classification.",)),
        "ground_classification_failed": (JobErrorCode.GROUND_CLASSIFICATION_FAILED.value, "Automatic ground classification did not produce enough reliable ground points.", ("Provide a DTM or review ground classification.",)),
        "preparation_validation_failed": (JobErrorCode.PREPARATION_VALIDATION_FAILED.value, "The prepared height values did not pass scientific quality checks.", ("Review preparation diagnostics and provide a DTM if appropriate.",)),
        "height above ground pipeline failed": (JobErrorCode.HAG_GENERATION_FAILED.value, "Height normalization failed during LiDAR preparation.", ("Review ground classification or provide a compatible DTM.",)),
    }
    if "dtm generation failed" in lowered or "invalid index to scalar" in lowered:
        return StructuredJobError(
            code=JobErrorCode.PRODUCT_EXECUTION_FAILED.value,
            user_message="DTM could not be generated because the ground-surface calculation returned an unexpected data structure.",
            technical_message=text,
            stage="DTM",
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            suggested_actions=("Review DTM product diagnostics.", "Retry with the corrected plugin build."),
            retryable=True,
        )
    if "scientific_runtime_boundary" in lowered or "required dependency is not importable" in lowered:
        return StructuredJobError(
            code=JobErrorCode.ENGINE_DEPENDENCY_MISSING.value,
            user_message="The Processing Engine is missing a required scientific dependency.",
            technical_message=text,
            stage="Processing Engine",
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            suggested_actions=("Open Settings and repair the Processing Engine.",),
            retryable=False,
        )
    if "engine_runtime_changed" in lowered or "runtime token" in lowered or "contract hash" in lowered:
        return StructuredJobError(
            code=JobErrorCode.ENGINE_RUNTIME_CHANGED.value,
            user_message="The Processing Engine changed after this job was prepared.",
            technical_message=text,
            stage="Processing Engine",
            exception_type=type(exc).__name__,
            traceback=traceback_text,
            suggested_actions=("Repair or refresh the Processing Engine, then start the job again.",),
            retryable=False,
        )
    for marker, (code, message, actions) in preparation_codes.items():
        if marker in lowered:
            return StructuredJobError(code=code, user_message=message, technical_message=text, stage="LiDAR Preparation", exception_type=type(exc).__name__, traceback=traceback_text, suggested_actions=actions, retryable=False)
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


def write_failure_artifacts(result: BatchResult, diagnostics_dir: Path) -> tuple[Path, Path] | None:
    """Write one readable error report and one bounded technical bundle."""
    if result.scientific_outcome == "SUCCEEDED":
        return None
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    error_report = diagnostics_dir / "error_report.html"
    bundle = diagnostics_dir / "technical_diagnostics.zip"
    products = tuple(product for item in result.items for product in item.product_results)
    rows = "".join(
        "<tr>"
        f"<td>{escape(product.product)}</td><td>{escape(product.status)}</td>"
        f"<td>{escape(product.message)}</td><td>{escape(product.error_code or 'None')}</td>"
        "</tr>"
        for product in products
    )
    successful = ", ".join(product.product for product in products if product.status == "SUCCEEDED") or "None"
    failed = ", ".join(product.product for product in products if product.status == "FAILED") or "None"
    write_text(
        error_report,
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>PyForestScan processing issue</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;color:#23313a;max-width:1000px}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #dfe6e9;padding:8px;text-align:left}"
        "th{background:#eef3f4}</style></head><body>"
        f"<h1>{escape(result.scientific_outcome.replace('_', ' ').title())}</h1>"
        f"<p><strong>Successful products:</strong> {escape(successful)}<br>"
        f"<strong>Failed products:</strong> {escape(failed)}<br>"
        f"<strong>Output folder:</strong> {escape(str(result.batch_folder))}</p>"
        "<p>Successful outputs were preserved. Attach the technical diagnostics ZIP when reporting a problem.</p>"
        f"<table><tr><th>Product</th><th>Status</th><th>Explanation</th><th>Error code</th></tr>{rows}</table>"
        "</body></html>",
    )
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for path in sorted(diagnostics_dir.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(path, path.relative_to(diagnostics_dir))
        for path in (result.summary_json, result.summary_html):
            if path.is_file():
                archive.write(path, Path("report") / path.name)
    return error_report, bundle


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
