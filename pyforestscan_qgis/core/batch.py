"""Batch processing models and discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .types import ProductType
from .workspace import RunContext

LIDAR_SUFFIXES = {".las", ".laz", ".copc"}


@dataclass(frozen=True)
class BatchDataset:
    """One lidar dataset discovered for a batch workflow."""

    path: Path
    selected: bool = True
    status: str = "discovered"
    bounds_summary: str = "Not inspected yet"
    message: str = ""


@dataclass(frozen=True)
class BatchProductSettings:
    """Shared product settings applied to every selected batch dataset."""

    products: tuple[ProductType, ...]
    grid_resolution: float
    height_bin_size: float | None = None
    chm_interpolation: str = "linear"
    chm_interpolate_valid_region: bool = False
    chm_clean_edges: bool = False
    canopy_cover_height_threshold: float = 2.0
    stop_on_error: bool = False
    load_outputs_into_qgis: bool = True
    execution_mode: str = "automatic"
    max_workers: int = 5
    confirm_large_parallel: bool = True
    skip_completed: bool = True
    retry_failed_only: bool = False
    overwrite_existing: bool = False
    preflight_acknowledged: bool = False


@dataclass(frozen=True)
class BatchRequest:
    """Input request for sequential batch processing."""

    input_folder: Path
    output_folder: Path
    recursive: bool
    datasets: tuple[Path, ...]
    settings: BatchProductSettings
    title: str = "PyForestScan Batch"
    batch_folder: Path | None = None


@dataclass(frozen=True)
class BatchItemResult:
    """Result for one dataset in a batch run."""

    dataset_path: Path
    run_context: RunContext
    status: str
    message: str
    outputs: tuple[Path, ...]
    bounds_summary: str = "Not inspected"
    requested_products: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchResult:
    """Summary of one sequential batch run."""

    batch_id: str
    title: str
    started_at: str
    finished_at: str
    batch_folder: Path
    items: tuple[BatchItemResult, ...]
    summary_json: Path
    summary_csv: Path
    summary_html: Path
    output_registry_path: Path | None = None
    load_outputs_after_completion: bool = False

    @property
    def success_count(self) -> int:
        """Return completed item count."""
        return len([item for item in self.items if item.status == "completed"])

    @property
    def failure_count(self) -> int:
        """Return failed item count."""
        return len([item for item in self.items if item.status == "failed"])

    @property
    def skipped_count(self) -> int:
        """Return skipped item count."""
        return len([item for item in self.items if item.status == "skipped"])

    @property
    def total_output_count(self) -> int:
        """Return the number of output artifacts recorded by all items."""
        return sum(len(item.outputs) for item in self.items)

    @property
    def total_estimated_output_bytes(self) -> int:
        """Return a best-effort total size for output artifacts that exist on disk."""
        total = 0
        for item in self.items:
            for path in item.outputs:
                try:
                    if path.exists() and path.is_file():
                        total += path.stat().st_size
                except OSError:
                    continue
        return total


def discover_lidar_files(input_folder: Path | str, recursive: bool = False) -> tuple[BatchDataset, ...]:
    """Discover LAS, LAZ, COPC, and EPT datasets in an input folder."""
    root = Path(input_folder)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {root}")
    iterator = root.rglob("*") if recursive else root.glob("*")
    datasets: list[BatchDataset] = []
    for path in iterator:
        if not path.is_file():
            continue
        if _is_lidar_path(path):
            datasets.append(BatchDataset(path=path))
    return tuple(sorted(datasets, key=lambda item: str(item.path).lower()))


def create_batch_folder(output_folder: Path | str, timestamp: datetime | None = None) -> Path:
    """Create a unique batch output folder."""
    root = Path(output_folder)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    parent = root / f"pyforestscan_batch_{stamp}"
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=False)
        return parent
    index = 2
    while True:
        candidate = root / f"pyforestscan_batch_{stamp}_{index:02d}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def batch_run_context(lidar_path: Path | str, batch_folder: Path | str, reuse_existing: bool = False) -> RunContext:
    """Create a run context directly under a batch folder for one dataset."""
    lidar = Path(lidar_path)
    batch = Path(batch_folder)
    run_folder = batch / _safe_run_name(lidar) if reuse_existing else _unique_child(batch, _safe_run_name(lidar))
    reports = run_folder / "reports"
    tables = run_folder / "tables"
    outputs = run_folder / "outputs"
    logs = run_folder / "logs"
    temp = run_folder / "temp"
    return RunContext(
        lidar_path=lidar,
        output_root=batch,
        run_folder=run_folder,
        reports_dir=reports,
        tables_dir=tables,
        outputs_dir=outputs,
        logs_dir=logs,
        temp_dir=temp,
        dataset_report_json=reports / "dataset_report.json",
        dataset_report_html=reports / "dataset_report.html",
        dataset_summary_csv=tables / "dataset_summary.csv",
        product_plan_json=reports / "product_plan.json",
        product_plan_html=reports / "product_plan.html",
        product_plan_csv=tables / "product_plan.csv",
        job_summary_json=logs / "job_summary.json",
        job_summary_html=logs / "job_summary.html",
    )


def _is_lidar_path(path: Path) -> bool:
    name = path.name.lower()
    if name == "ept.json":
        return True
    if name.endswith(".copc.laz"):
        return True
    return path.suffix.lower() in LIDAR_SUFFIXES


def _safe_run_name(path: Path) -> str:
    import re

    stem = path.parent.name if path.name.lower() == "ept.json" and path.parent.name else path.stem
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "dataset"


def _unique_child(parent: Path, base_name: str) -> Path:
    candidate = parent / base_name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = parent / f"{base_name}_{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1
