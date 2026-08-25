"""Durable completed-job summary derived without querying live widgets."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from .output_registry import read_output_registry


@dataclass(frozen=True)
class CompletedJobSummary:
    logical_job_id: str
    attempt_id: str
    repository: str
    polygon_area: float | None
    requested_products: tuple[str, ...]
    requested_concurrency: int
    effective_concurrency: int
    processing_profile: str
    processing_strategy: str
    work_units_total: int
    work_units_completed: int
    work_units_failed: int
    work_units_skipped: int
    elapsed_time: float | None
    final_outputs: tuple[Path, ...]
    secondary_outputs: tuple[Path, ...]
    warnings: tuple[str, ...]
    terminal_state: str


def completed_job_summary(result, preflight_report=None, *, processing_profile: str = "Automatic") -> CompletedJobSummary:
    """Build a presentation model from terminal result, plan, checkpoints, and registry."""
    execution_plan = getattr(preflight_report, "execution_plan", None)
    request = getattr(preflight_report, "request", None)
    products = tuple(str(getattr(item, "value", item)) for item in getattr(request, "products", ()))
    repository = str(getattr(request, "lidar_folder", "") or "")
    polygon = getattr(request, "polygon", None)
    area = float(getattr(polygon, "area")) if polygon is not None and getattr(polygon, "area", None) is not None else None
    requested = int(getattr(execution_plan, "requested_concurrency", 0) or getattr(preflight_report, "max_workers", 1) or 1)
    effective = int(getattr(execution_plan, "effective_concurrency", 0) or getattr(preflight_report, "recommended_workers", requested) or requested)
    strategy = str(getattr(getattr(preflight_report, "execution_plan", None), "spatial_read_plan", {}).get("strategy", ""))
    if not strategy:
        strategy = str(getattr(preflight_report, "execution_mode", "durable adaptive" if execution_plan is not None else "sequential"))
    counts = _work_unit_counts(result)
    registry = _registry_outputs(result)
    primary = tuple(item.path for item in registry if getattr(item, "output_role", "primary") == "primary" and item.valid and item.complete)
    secondary = tuple(item.path for item in registry if getattr(item, "output_role", "primary") == "secondary" and item.valid and item.complete)
    if not primary:
        primary = tuple(Path(path) for item in getattr(result, "items", ()) if getattr(item, "status", "") == "completed" for path in getattr(item, "outputs", ()) if Path(path).suffix.lower() in {".tif", ".tiff"})
    if not secondary:
        secondary = tuple(Path(path) for item in getattr(result, "items", ()) if getattr(item, "status", "") == "completed" for path in getattr(item, "outputs", ()) if Path(path).suffix.lower() == ".csv")
    warnings = list(getattr(preflight_report, "warnings", ()) if preflight_report is not None else ())
    warnings.extend(str(getattr(item, "message", "")) for item in getattr(result, "items", ()) if "warning" in str(getattr(item, "message", "")).lower() or "recover" in str(getattr(item, "message", "")).lower())
    failed = int(getattr(result, "failure_count", 0))
    terminal = "FAILED" if failed else ("COMPLETE_WITH_WARNING" if warnings else "COMPLETE")
    attempt = next((str(getattr(item, "attempt_id", "")) for item in registry if getattr(item, "attempt_id", "")), "attempt-1")
    return CompletedJobSummary(str(getattr(result, "batch_id", "")), attempt, repository or _result_repository(result), area, products or _infer_products(primary, secondary), requested, effective, processing_profile, strategy, counts[0], counts[1], counts[2], counts[3], _elapsed_seconds(result), primary, secondary, tuple(dict.fromkeys(warnings)), terminal)


def format_completed_job_summary(summary: CompletedJobSummary) -> str:
    area = "Not recorded" if summary.polygon_area is None else f"{summary.polygon_area / 10000:.3g} ha"
    elapsed = "Not recorded" if summary.elapsed_time is None else f"{summary.elapsed_time:.1f} s"
    return (
        f"{summary.terminal_state.replace('_', ' ')} - {', '.join(summary.requested_products) or 'Products'}; "
        f"work units {summary.work_units_completed}/{summary.work_units_total} complete, {summary.work_units_failed} failed, {summary.work_units_skipped} skipped. "
        f"Repository: {Path(summary.repository).name if summary.repository else 'Not recorded'}; area: {area}. "
        f"Profile: {summary.processing_profile}; strategy: {summary.processing_strategy}; concurrency requested/effective: {summary.requested_concurrency}/{summary.effective_concurrency}. "
        f"Primary outputs: {len(summary.final_outputs)}; secondary outputs: {len(summary.secondary_outputs)}; elapsed: {elapsed}."
    )


def _registry_outputs(result):
    path = getattr(result, "output_registry_path", None)
    try: return read_output_registry(path) if path and Path(path).is_file() else ()
    except (OSError, ValueError, TypeError): return ()


def _work_unit_counts(result) -> tuple[int, int, int, int]:
    statuses=[]
    for item in getattr(result, "items", ()):
        root=Path(getattr(getattr(item, "run_context", None), "run_folder", ""))/"work_units"
        for path in root.glob("*/status.json") if root.is_dir() else ():
            try: statuses.append(str(json.loads(path.read_text(encoding="utf-8")).get("status", "")))
            except (OSError,ValueError): pass
    if not statuses:
        total=len(getattr(result,"items",()));completed=int(getattr(result,"success_count",0));failed=int(getattr(result,"failure_count",0));skipped=int(getattr(result,"skipped_count",0));return total,completed,failed,skipped
    complete=sum(item in {"Complete","CompleteNoData"} for item in statuses);failed=sum(item=="Failed" for item in statuses);skipped=sum(item=="SkippedOutsidePolygon" for item in statuses)
    return len(statuses),complete,failed,skipped


def _elapsed_seconds(result) -> float | None:
    try:return max(0.0,(datetime.fromisoformat(result.finished_at)-datetime.fromisoformat(result.started_at)).total_seconds())
    except (AttributeError,TypeError,ValueError):return None


def _result_repository(result) -> str:
    return str(next((getattr(item,"dataset_path","") for item in getattr(result,"items",()) if getattr(item,"dataset_path",None)),""))


def _infer_products(primary,secondary):
    names=[path.stem.lower() for path in (*primary,*secondary)]
    return tuple(dict.fromkeys("rumple" if "rumple" in name else "chm" if "chm" in name else name for name in names))


__all__=["CompletedJobSummary","completed_job_summary","format_completed_job_summary"]
