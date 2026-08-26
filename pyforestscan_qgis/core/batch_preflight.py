"""Batch preflight validation and resume planning."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchRequest, batch_run_context, create_batch_folder
from .batch_executor import LARGE_FILE_COUNT, LARGE_WORKLOAD_SCORE, BatchExecutor, PARALLEL_SAFE_MODE
from .external_worker import (
    EXTERNAL_WORKER_DISABLED_MESSAGE,
    EXTERNAL_WORKER_MODE,
    check_worker_readiness,
    external_workers_enabled,
)
from .batch_manifest import MANIFEST_NAME, completed_dataset_paths, failed_dataset_paths, load_manifest
from .dataset_report import build_dataset_explorer_report, report_to_dict

DiskUsageProvider = Callable[[Path], tuple[int, int, int]]


@dataclass(frozen=True)
class BatchPreflightReport:
    """Result of checking whether a batch can start safely."""

    batch_folder: Path
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    estimated_output_bytes: int
    free_disk_bytes: int
    files_to_process: tuple[Path, ...]
    files_completed: tuple[Path, ...]
    files_to_skip: tuple[Path, ...]
    files_to_retry: tuple[Path, ...]
    manifest_path: Path
    execution_mode: str
    max_workers: int
    recommended_workers: int
    processing_spatial_contexts: tuple[tuple[str, dict[str, object]], ...] = ()

    @property
    def has_warnings(self) -> bool:
        """Return whether warnings require user acknowledgement."""
        return bool(self.warnings)


def run_batch_preflight(
    request: BatchRequest,
    adapter: PyForestScanAdapter | None = None,
    disk_usage_provider: DiskUsageProvider | None = None,
) -> BatchPreflightReport:
    """Run preflight checks before creating or resuming a batch."""
    adapter = adapter or PyForestScanAdapter()
    disk_usage_provider = disk_usage_provider or _disk_usage
    blockers: list[str] = []
    warnings: list[str] = []
    if not request.datasets:
        blockers.append("Select at least one lidar file.")
    missing = [str(path) for path in request.datasets if not Path(path).exists()]
    if missing:
        blockers.append("Missing input file(s): " + "; ".join(missing[:5]))
    if not request.settings.products:
        blockers.append("Select at least one product.")
    try:
        request.output_folder.mkdir(parents=True, exist_ok=True)
        probe = request.output_folder / ".pyforestscan_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        blockers.append(f"Output folder is not writable: {exc}")
    # A new immutable request always receives a new identity. Historical
    # manifests are consulted only when the caller explicitly selects one.
    batch_folder = request.batch_folder or create_batch_folder(request.output_folder)
    manifest_path = batch_folder / MANIFEST_NAME
    completed: tuple[Path, ...] = ()
    failed: tuple[Path, ...] = ()
    if manifest_path.exists():
        try:
            manifest = load_manifest(manifest_path)
            completed = completed_dataset_paths(manifest)
            failed = failed_dataset_paths(manifest)
        except (OSError, ValueError, KeyError) as exc:
            blockers.append(f"Existing batch manifest could not be read: {exc}")
    files_to_process = tuple(Path(path) for path in request.datasets)
    files_to_skip: tuple[Path, ...] = ()
    files_to_retry: tuple[Path, ...] = ()
    if request.settings.skip_completed and completed:
        files_to_skip = tuple(path for path in files_to_process if path in completed)
        files_to_process = tuple(path for path in files_to_process if path not in completed)
    if request.settings.retry_failed_only:
        files_to_retry = tuple(path for path in files_to_process if path in failed)
        files_to_process = files_to_retry
    conflicts = _output_conflicts(files_to_process, batch_folder, request.settings.overwrite_existing)
    if conflicts:
        blockers.append("Output conflicts detected: " + "; ".join(str(path) for path in conflicts[:5]))
    estimate = estimate_batch_output_bytes(request, len(files_to_process))
    try:
        free_disk = disk_usage_provider(request.output_folder)[2]
        if estimate > 0 and free_disk < int(estimate * 1.2):
            blockers.append("Free disk space is below the estimated output requirement plus safety margin.")
    except OSError as exc:
        free_disk = 0
        warnings.append(f"Free disk space could not be checked: {exc}")
    try:
        readiness = adapter.check_environment().readiness.value
        backend = adapter.selected_execution_backend() if hasattr(adapter, "selected_execution_backend") else "qgis_python"
        if readiness == "NOT READY":
            blockers.append(f"Environment is {readiness}; run Environment Check before batch processing.")
        elif readiness != "READY" and backend == "pbm_backend":
            warnings.append("QGIS Python scientific dependencies are not READY, but PBM backend is READY and will be used for routed products.")
    except Exception as exc:  # noqa: BLE001 - preflight reports environment uncertainty.
        warnings.append(f"Environment readiness could not be verified: {exc}")
    spatial_contexts = _check_preparation_spatial_readiness(request, files_to_process, adapter, blockers, warnings)
    workload_score = len(files_to_process) * max(1, len(request.settings.products))
    if len(files_to_process) >= LARGE_FILE_COUNT:
        warnings.append("Large batch: many files selected.")
    if workload_score >= LARGE_WORKLOAD_SCORE:
        warnings.append("Large workload: many file/product combinations selected.")
    if request.settings.execution_mode == PARALLEL_SAFE_MODE:
        warnings.append("Parallel safe mode can increase memory, CPU, and disk pressure.")
    if request.settings.execution_mode == EXTERNAL_WORKER_MODE:
        if not external_workers_enabled():
            blockers.append(EXTERNAL_WORKER_DISABLED_MESSAGE)
        else:
            ok, message = check_worker_readiness()
            if not ok:
                blockers.append(f"External worker readiness check failed: {message}")
            else:
                warnings.append(f"External worker readiness: {message}")
            warnings.append("External worker mode starts separate Python processes and can multiply RAM, CPU, and disk use.")
    try:
        guardrail = BatchExecutor().guardrails(request)
        warnings.extend(guardrail.warnings)
        if guardrail.blocked:
            warnings.append(guardrail.reason or "Parallel safe mode requires confirmation.")
    except Exception as exc:  # noqa: BLE001 - guardrail validation is a blocker.
        blockers.append(str(exc))
    return BatchPreflightReport(
        batch_folder=batch_folder,
        ready=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        estimated_output_bytes=estimate,
        free_disk_bytes=free_disk,
        files_to_process=files_to_process,
        files_completed=completed,
        files_to_skip=files_to_skip,
        files_to_retry=files_to_retry,
        manifest_path=manifest_path,
        execution_mode=request.settings.execution_mode,
        max_workers=request.settings.max_workers,
        recommended_workers=recommend_batch_workers(len(files_to_process), workload_score, request.settings.execution_mode),
        processing_spatial_contexts=spatial_contexts,
    )


def estimate_batch_output_bytes(request: BatchRequest, file_count: int | None = None) -> int:
    """Return conservative estimated output storage for preflight."""
    count = len(request.datasets) if file_count is None else file_count
    if count <= 0:
        return 0
    product_count = len(request.settings.products)
    # Preflight does not inspect every file. Use a deliberately conservative
    # per-product placeholder that can be replaced by calibrated estimates later.
    per_product_bytes = 128 * 1024 * 1024
    if any(product.value == "pad" for product in request.settings.products):
        per_product_bytes += 256 * 1024 * 1024
    return count * max(1, product_count) * per_product_bytes


def _output_conflicts(datasets: tuple[Path, ...], batch_folder: Path, overwrite_existing: bool) -> tuple[Path, ...]:
    if overwrite_existing:
        return ()
    conflicts: list[Path] = []
    for dataset in datasets:
        context = batch_run_context(dataset, batch_folder, reuse_existing=True)
        if context.outputs_dir.exists() and any(context.outputs_dir.iterdir()):
            conflicts.append(context.outputs_dir)
    return tuple(conflicts)


def _disk_usage(path: Path) -> tuple[int, int, int]:
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free


def recommend_batch_workers(file_count: int, workload_score: int, execution_mode: str) -> int:
    """Recommend a conservative worker count for preflight display."""
    if file_count <= 1:
        return 1
    if workload_score >= LARGE_WORKLOAD_SCORE or file_count >= LARGE_FILE_COUNT:
        return 2
    if execution_mode == EXTERNAL_WORKER_MODE:
        return min(4, file_count)
    return min(3, file_count) if workload_score <= 8 else 2


def _check_preparation_spatial_readiness(request, sources, adapter, blockers, warnings) -> tuple[tuple[str, dict[str, object]], ...]:
    """Surface resolvable unit metadata before a PBM worker starts."""
    products = {str(getattr(item, "value", item)) for item in request.settings.products}
    if not products.intersection({"chm", "rumple", "pad", "pai", "fhd", "canopy_cover", "voxel_stat"}):
        return ()
    unresolved: list[Path] = []
    resolved_contexts: list[tuple[str, dict[str, object]]] = []
    inspected = tuple(sources[:50])
    for source in inspected:
        try:
            report = build_dataset_explorer_report(adapter.inspect_dataset(source), requested_products=tuple(products))
        except Exception as exc:  # noqa: BLE001 - ordinary metadata uncertainty is reported, not fatal.
            warnings.append(f"Preparation metadata could not be checked for {Path(source).name}: {exc}")
            continue
        if report.preparation_readiness == "NEEDS_USER_INPUT":
            unresolved.append(Path(source))
        preparation = report_to_dict(report).get("preparation", {}) if hasattr(report, "source_coordinate_units") else {}
        if isinstance(preparation, dict) and preparation:
            basis = str(preparation.get("source_units_basis", "UNRESOLVED"))
            resolved_contexts.append((str(Path(source)), {
                "crs": report.crs or "",
                "linear_units": str(preparation.get("source_coordinate_units", "")),
                "unit_basis": basis,
                "confidence": "ASSUMED" if basis == "ASSUMED_SOURCE_LOCAL" else ("HIGH" if preparation.get("source_units_authoritative") else "NONE"),
                "source_units_authoritative": bool(preparation.get("source_units_authoritative")),
                "georeferenced": bool(report.crs),
                "processing_coordinate_mode": str(preparation.get("processing_coordinate_mode", "unresolved")),
                "distance_operations_safe": report.preparation_readiness not in {"NEEDS_USER_INPUT", "BLOCKED"},
                "fallback_applied": basis == "ASSUMED_SOURCE_LOCAL",
                "warnings": tuple(item.message for item in report.warnings if item.code == "SOURCE_UNITS_ASSUMED"),
                "blockers": (),
            }))
        for item in getattr(report, "warnings", ()):
            if item.code == "SOURCE_UNITS_ASSUMED":
                warnings.append(item.message)
    if unresolved:
        names = ", ".join(path.name for path in unresolved[:5])
        blockers.append(f"SOURCE_UNITS_UNKNOWN: PyForestScan found usable preparation inputs for {names}. Choose trusted coordinate units or assign the source coordinate system to continue.")
    if len(sources) > len(inspected):
        warnings.append(f"Preparation metadata was checked for the first {len(inspected)} selected sources; repository assignments will be revalidated during execution.")
    return tuple(resolved_contexts)


def _recommended_workers(file_count: int, workload_score: int, execution_mode: str) -> int:
    """Backward-compatible alias for older tests and integrations."""
    return recommend_batch_workers(file_count, workload_score, execution_mode)
