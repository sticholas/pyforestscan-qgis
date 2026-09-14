"""QGIS-free helpers for Mission Control result loading and compact summaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..core.dataset_report import DatasetExplorerReport, format_count_for_display, format_crs_for_display
from ..core.output_registry import REGISTRY_NAME, read_output_registry

RASTER_SUFFIXES = frozenset({".tif", ".tiff"})
TABLE_SUFFIXES = frozenset({".csv"})


@dataclass(frozen=True)
class LoadableOutput:
    """A result file that Mission Control can add to QGIS."""

    path: Path
    result_type: str
    layer_kind: str


def infer_output_result_type(path: Path, result_type: str | None = None) -> str:
    """Return the product result type used for styling and layer naming."""
    if result_type:
        return result_type
    stem = path.stem.lower()
    if "canopy_cover" in stem:
        return "canopy_cover_geotiff"
    if stem == "pad" or "pad" in stem:
        return "pad_geotiff"
    if stem == "pai" or "pai" in stem:
        return "pai_geotiff"
    if stem == "fhd" or "fhd" in stem:
        return "fhd_geotiff"
    if stem == "dtm" or "dtm" in stem:
        return "dtm_geotiff"
    if "point_density" in stem:
        return "point_density_geotiff"
    if "voxel" in stem:
        return "voxel_stat_geotiff"
    if "rumple" in stem:
        return "rumple_csv" if path.suffix.lower()==".csv" else "rumple_geotiff"
    return "chm_geotiff"


def collect_loadable_outputs(
    paths: Iterable[Path],
    result_types: dict[Path, str] | None = None,
    existing_sources: Iterable[Path | str] = (),
    primary_only: bool = False,
) -> tuple[LoadableOutput, ...]:
    """Return unique, not-yet-loaded raster/table outputs in stable order."""
    result_types = result_types or {}
    seen: set[str] = set()
    existing = {_normalize_path(source) for source in existing_sources}
    outputs: list[LoadableOutput] = []
    expanded_paths: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.name == REGISTRY_NAME and path.exists():
            try:
                expanded_paths.extend(output.path for output in read_output_registry(path) if output.complete and output.valid and (not primary_only or getattr(output,"output_role","primary")=="primary"))
            except Exception:
                pass
        else:
            expanded_paths.append(path)
    for path in expanded_paths:
        key = _normalize_path(path)
        if key in seen or key in existing:
            continue
        suffix = path.suffix.lower()
        if primary_only and suffix in TABLE_SUFFIXES:
            continue
        if suffix in RASTER_SUFFIXES:
            outputs.append(LoadableOutput(path, infer_output_result_type(path, result_types.get(path)), "raster"))
            seen.add(key)
        elif suffix in TABLE_SUFFIXES:
            outputs.append(LoadableOutput(path, infer_output_result_type(path, result_types.get(path)), "table"))
            seen.add(key)
    return tuple(outputs)


def output_loading_summary(loaded_count: int, candidate_count: int, *, already_loaded_count: int = 0, skipped_count: int = 0, failed_count: int = 0) -> str:
    """Return concise Load Outputs feedback with optional per-state counts."""
    if any((already_loaded_count, skipped_count, failed_count)):
        return "\n".join((
            f"Loaded: {loaded_count}",
            f"Already loaded: {already_loaded_count}",
            f"Skipped: {skipped_count}",
            f"Failed: {failed_count}",
        ))
    if loaded_count > 0:
        noun = "output" if loaded_count == 1 else "outputs"
        return f"Loaded {loaded_count} {noun} into QGIS."
    if candidate_count > 0:
        return "No new loadable outputs found."
    return "No loadable outputs found."


def compact_dataset_summary_lines(report: DatasetExplorerReport) -> tuple[str, ...]:
    """Return compact key facts for the Dataset page summary card."""
    filename = Path(report.source_path).name or "Unknown"
    readiness = _dataset_readiness(report)
    return (
        f"File: {filename}",
        f"Format: {report.source_format.upper()}",
        f"CRS: {format_crs_for_display(report.crs)}",
        f"Point count: {format_count_for_display(report.point_count)}",
        f"Bounds: {_format_bounds(report)}",
        f"Readiness: {readiness}",
    )


def _dataset_readiness(report: DatasetExplorerReport) -> str:
    if any(warning.severity.lower() == "error" for warning in report.warnings):
        return "Needs attention"
    if report.warnings:
        return "Ready with warnings"
    return "Ready"


def _format_bounds(report: DatasetExplorerReport) -> str:
    bounds = report.bounds
    if bounds is None:
        return "Unknown"
    return f"X {bounds.min_x:.2f} to {bounds.max_x:.2f}; Y {bounds.min_y:.2f} to {bounds.max_y:.2f}; Z {bounds.min_z:.2f} to {bounds.max_z:.2f}"


def _normalize_path(path: Path | str) -> str:
    text = str(path).split("|", 1)[0]
    try:
        return str(Path(text).expanduser().resolve()).casefold()
    except OSError:
        return str(Path(text).expanduser()).casefold()
