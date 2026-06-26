"""Run-folder workspace context for Mission Control workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunContext:
    """Paths for one Mission Control run folder."""

    lidar_path: Path
    output_root: Path
    run_folder: Path
    reports_dir: Path
    tables_dir: Path
    outputs_dir: Path
    logs_dir: Path
    temp_dir: Path
    dataset_report_json: Path
    dataset_report_html: Path
    dataset_summary_csv: Path
    product_plan_json: Path
    product_plan_html: Path
    product_plan_csv: Path
    job_summary_json: Path

    def ensure_directories(self) -> "RunContext":
        """Create the run folder directory structure and return this context."""
        for path in (self.reports_dir, self.tables_dir, self.outputs_dir, self.logs_dir, self.temp_dir):
            path.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def friendly_links(self) -> tuple[tuple[str, Path], ...]:
        """Return user-facing result labels and paths."""
        return (
            ("Dataset Report", self.dataset_report_html),
            ("Product Plan", self.product_plan_html),
            ("Job Summary", self.job_summary_json),
            ("Output Folder", self.run_folder),
            ("Products", self.outputs_dir),
        )

    @property
    def advanced_paths(self) -> tuple[tuple[str, Path], ...]:
        """Return internal paths for advanced troubleshooting."""
        return (
            ("Dataset JSON", self.dataset_report_json),
            ("Dataset HTML", self.dataset_report_html),
            ("Dataset CSV", self.dataset_summary_csv),
            ("Product Plan JSON", self.product_plan_json),
            ("Product Plan HTML", self.product_plan_html),
            ("Product Plan CSV", self.product_plan_csv),
            ("Job Summary JSON", self.job_summary_json),
            ("Run Folder", self.run_folder),
            ("Temp Folder", self.temp_dir),
        )


def create_run_context(
    lidar_path: Path | str,
    output_root: Path | str,
    timestamp: datetime | None = None,
) -> RunContext:
    """Create a timestamped run context for a lidar dataset and output root."""
    lidar = Path(lidar_path)
    root = Path(output_root)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    dataset_stem = _safe_stem(lidar)
    run_folder = _unique_run_folder(root / "pyforestscan_runs", f"{stamp}_{dataset_stem}")
    reports = run_folder / "reports"
    tables = run_folder / "tables"
    outputs = run_folder / "outputs"
    logs = run_folder / "logs"
    temp = run_folder / "temp"
    return RunContext(
        lidar_path=lidar,
        output_root=root,
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
    )


def _safe_stem(path: Path) -> str:
    stem = path.stem or "dataset"
    if path.name.lower() == "ept.json" and path.parent.name:
        stem = path.parent.name
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "dataset"


def _unique_run_folder(parent: Path, base_name: str) -> Path:
    """Return a run folder path that will not overwrite an existing run."""
    candidate = parent / base_name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = parent / f"{base_name}_{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1
