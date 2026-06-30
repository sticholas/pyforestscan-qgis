"""External worker job specifications and process helpers."""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .batch import BatchItemResult, BatchProductSettings, batch_run_context
from .types import ProductType

EXTERNAL_WORKER_MODE = "external_worker"
WORKER_JOBS_DIR = "worker_jobs"
WORKER_RESULTS_DIR = "worker_results"
DEFAULT_WORKER_TIMEOUT_SECONDS = 60 * 60 * 6
MAX_EXTERNAL_WORKERS = 6


@dataclass(frozen=True)
class ExternalWorkerJobSpec:
    """Serializable job specification for one external worker process."""

    job_id: str
    input_lidar_path: Path
    batch_folder: Path
    run_folder: Path
    products: tuple[ProductType, ...]
    grid_resolution: float
    height_bin_size: float | None
    chm_interpolation: str
    chm_interpolate_valid_region: bool
    chm_clean_edges: bool
    canopy_cover_height_threshold: float
    overwrite_existing: bool
    plugin_version: str | None
    pyforestscan_version: str | None

    @property
    def spec_path(self) -> Path:
        """Return the default spec JSON path."""
        return self.batch_folder / WORKER_JOBS_DIR / f"{self.job_id}.json"

    @property
    def result_path(self) -> Path:
        """Return the default worker result JSON path."""
        return self.batch_folder / WORKER_RESULTS_DIR / f"{self.job_id}_result.json"


@dataclass(frozen=True)
class ExternalWorkerResult:
    """Serializable result written by an external worker process."""

    job_id: str
    dataset_path: Path
    run_folder: Path
    status: str
    started_at: str
    finished_at: str
    outputs: tuple[Path, ...]
    error_message: str | None = None
    log_messages: tuple[str, ...] = ()


def build_worker_job_spec(job_id: str, dataset_path: Path, batch_folder: Path, settings: BatchProductSettings) -> ExternalWorkerJobSpec:
    """Build a worker job spec from a dataset and shared batch settings."""
    context = batch_run_context(dataset_path, batch_folder, reuse_existing=True)
    return ExternalWorkerJobSpec(
        job_id=job_id,
        input_lidar_path=Path(dataset_path),
        batch_folder=Path(batch_folder),
        run_folder=context.run_folder,
        products=settings.products,
        grid_resolution=settings.grid_resolution,
        height_bin_size=settings.height_bin_size,
        chm_interpolation=settings.chm_interpolation,
        chm_interpolate_valid_region=settings.chm_interpolate_valid_region,
        chm_clean_edges=settings.chm_clean_edges,
        canopy_cover_height_threshold=settings.canopy_cover_height_threshold,
        overwrite_existing=settings.overwrite_existing,
        plugin_version=_package_version("pyforestscan-qgis"),
        pyforestscan_version=_package_version("pyforestscan"),
    )


def write_worker_job_spec(spec: ExternalWorkerJobSpec, path: Path | str | None = None) -> Path:
    """Write a worker job spec JSON file."""
    output = Path(path) if path is not None else spec.spec_path
    output.parent.mkdir(parents=True, exist_ok=True)
    spec.result_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(worker_job_spec_to_dict(spec), indent=2), encoding="utf-8")
    return output


def load_worker_job_spec(path: Path | str) -> ExternalWorkerJobSpec:
    """Load a worker job spec from JSON."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExternalWorkerJobSpec(
        job_id=str(payload["job_id"]),
        input_lidar_path=Path(payload["input_lidar_path"]),
        batch_folder=Path(payload["batch_folder"]),
        run_folder=Path(payload["run_folder"]),
        products=tuple(ProductType(value) for value in payload.get("products", [])),
        grid_resolution=float(payload["parameters"]["grid_resolution"]),
        height_bin_size=payload["parameters"].get("height_bin_size"),
        chm_interpolation=str(payload["parameters"].get("chm_interpolation", "linear")),
        chm_interpolate_valid_region=bool(payload["parameters"].get("chm_interpolate_valid_region", False)),
        chm_clean_edges=bool(payload["parameters"].get("chm_clean_edges", False)),
        canopy_cover_height_threshold=float(payload["parameters"].get("canopy_cover_height_threshold", 2.0)),
        overwrite_existing=bool(payload.get("overwrite_existing", False)),
        plugin_version=payload.get("plugin_version"),
        pyforestscan_version=payload.get("pyforestscan_version"),
    )


def worker_job_spec_to_dict(spec: ExternalWorkerJobSpec) -> dict[str, Any]:
    """Convert worker spec to JSON-serializable data."""
    return {
        "job_id": spec.job_id,
        "input_lidar_path": str(spec.input_lidar_path),
        "batch_folder": str(spec.batch_folder),
        "run_folder": str(spec.run_folder),
        "products": [product.value for product in spec.products],
        "parameters": {
            "grid_resolution": spec.grid_resolution,
            "height_bin_size": spec.height_bin_size,
            "chm_interpolation": spec.chm_interpolation,
            "chm_interpolate_valid_region": spec.chm_interpolate_valid_region,
            "chm_clean_edges": spec.chm_clean_edges,
            "canopy_cover_height_threshold": spec.canopy_cover_height_threshold,
        },
        "overwrite_existing": spec.overwrite_existing,
        "plugin_version": spec.plugin_version,
        "pyforestscan_version": spec.pyforestscan_version,
        "result_path": str(spec.result_path),
    }


def write_worker_result(result: ExternalWorkerResult, path: Path | str) -> Path:
    """Write a worker result JSON file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(worker_result_to_dict(result), indent=2), encoding="utf-8")
    return output


def load_worker_result(path: Path | str) -> ExternalWorkerResult:
    """Load a worker result JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ExternalWorkerResult(
        job_id=str(payload["job_id"]),
        dataset_path=Path(payload["dataset_path"]),
        run_folder=Path(payload["run_folder"]),
        status=str(payload["status"]),
        started_at=str(payload.get("started_at", "")),
        finished_at=str(payload.get("finished_at", "")),
        outputs=tuple(Path(value) for value in payload.get("outputs", [])),
        error_message=payload.get("error_message"),
        log_messages=tuple(str(item) for item in payload.get("log_messages", [])),
    )


def worker_result_to_dict(result: ExternalWorkerResult) -> dict[str, Any]:
    """Convert worker result to JSON-serializable data."""
    return {
        "job_id": result.job_id,
        "dataset_path": str(result.dataset_path),
        "run_folder": str(result.run_folder),
        "status": result.status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "outputs": [str(path) for path in result.outputs],
        "error_message": result.error_message,
        "log_messages": list(result.log_messages),
    }


def worker_result_to_batch_item(result: ExternalWorkerResult, batch_folder: Path) -> BatchItemResult:
    """Convert a worker result into the normal batch item record."""
    context = batch_run_context(result.dataset_path, batch_folder, reuse_existing=True).ensure_directories()
    message = result.error_message or result.status
    return BatchItemResult(result.dataset_path, context, result.status, message, result.outputs, "Worker result")


def worker_check_command(python_executable: Path | str | None = None) -> list[str]:
    """Return the command used to check worker readiness."""
    executable = str(python_executable or sys.executable)
    return [executable, "-m", "pyforestscan_qgis.worker.run_job", "--check"]


def worker_run_command(spec_path: Path | str, python_executable: Path | str | None = None) -> list[str]:
    """Return the command used to run one external worker job."""
    executable = str(python_executable or sys.executable)
    return [executable, "-m", "pyforestscan_qgis.worker.run_job", "--spec", str(spec_path)]


def check_worker_readiness(python_executable: Path | str | None = None, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Run the worker entrypoint --check command."""
    try:
        completed = subprocess.run(worker_check_command(python_executable), capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except Exception as exc:  # noqa: BLE001 - preflight needs a user-facing reason.
        return False, str(exc)
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output or f"exit code {completed.returncode}"


def utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
