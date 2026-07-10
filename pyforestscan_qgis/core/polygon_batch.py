"""Polygon area batch preflight and execution helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .adapter import PyForestScanAdapter
from .batch import BatchProductSettings, BatchRequest, BatchResult, create_batch_folder
from .batch_executor import BatchExecutor
from .lidar_inventory import LidarFolderRequest, LidarInventory, LidarSourceRecord, discover_lidar_sources
from .polygon_processing import PolygonProcessingPlan, build_polygon_processing_plan
from .polygon_source import NormalizedPolygonSelection
from .types import HagNormalizationRequest, ProductType

POLYGON_MANIFEST_NAME = "polygon_batch_manifest.json"
DEFAULT_POLYGON_SOURCE_WARNING = 25
DEFAULT_POLYGON_POINT_WARNING = 25_000_000
DEFAULT_POLYGON_SIZE_WARNING_BYTES = 20 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class PolygonBatchRequest:
    """Request to run Batch from a folder clipped by one polygon."""

    lidar_folder: Path
    output_folder: Path
    polygon: NormalizedPolygonSelection
    products: tuple[ProductType, ...]
    settings: BatchProductSettings
    recursive: bool = True
    batch_folder: Path | None = None
    title: str = "PyForestScan Polygon Batch"


@dataclass(frozen=True)
class PolygonBatchPreflightReport:
    """Readiness report for polygon area processing."""

    request: PolygonBatchRequest
    inventory: LidarInventory
    plan: PolygonProcessingPlan
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    selected_sources: tuple[LidarSourceRecord, ...]
    skipped_sources: tuple[LidarSourceRecord, ...]
    estimated_point_count: int | None
    estimated_source_bytes: int
    batch_folder: Path
    manifest_path: Path

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def run_polygon_batch_preflight(request: PolygonBatchRequest) -> PolygonBatchPreflightReport:
    """Discover sources, intersect them with the polygon, and assess readiness."""
    inventory = discover_lidar_sources(LidarFolderRequest(request.lidar_folder, recursive=request.recursive, include_ept=True))
    plan = build_polygon_processing_plan(
        inventory,
        request.polygon.to_polygon_selection(),
        request.output_folder,
        tuple(product.value for product in request.products),
        processing_crs=request.polygon.processing_crs,
    )
    selected = plan.selected_sources
    skipped = tuple(source for source in inventory.sources if source not in selected)
    blockers: list[str] = []
    warnings: list[str] = list(plan.warnings)
    if not request.products:
        blockers.append("Select at least one product.")
    if not inventory.sources:
        blockers.append("No LiDAR sources were discovered in the selected folder.")
    if not selected:
        blockers.append("No discovered LiDAR sources intersect the selected polygon bounds.")
    if any(source.bounds is None for source in inventory.sources):
        warnings.append("Some sources have unknown bounds and are skipped until metadata inventory can prove intersection.")
    if any(source.crs and source.crs != request.polygon.processing_crs for source in selected):
        warnings.append("At least one intersecting source CRS differs from the polygon processing CRS; clipped extraction will request reprojection.")
    point_count = _estimated_points(selected)
    source_bytes = sum(source.size_bytes for source in selected)
    if len(selected) >= DEFAULT_POLYGON_SOURCE_WARNING:
        warnings.append("Large polygon batch: many intersecting sources selected.")
    if point_count is not None and point_count >= DEFAULT_POLYGON_POINT_WARNING:
        warnings.append("Large polygon batch: estimated point count is high; run sequentially unless carefully tested.")
    if source_bytes >= DEFAULT_POLYGON_SIZE_WARNING_BYTES:
        warnings.append("Large polygon batch: source file size is high; ensure disk and memory headroom.")
    batch_folder = request.batch_folder or _planned_polygon_batch_folder(request.output_folder)
    manifest_path = batch_folder / POLYGON_MANIFEST_NAME
    return PolygonBatchPreflightReport(
        request=request,
        inventory=inventory,
        plan=plan,
        ready=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        selected_sources=selected,
        skipped_sources=skipped,
        estimated_point_count=point_count,
        estimated_source_bytes=source_bytes,
        batch_folder=batch_folder,
        manifest_path=manifest_path,
    )


def polygon_preflight_text(report: PolygonBatchPreflightReport) -> str:
    """Format a concise Batch-page polygon preflight report."""
    point_text = "unknown" if report.estimated_point_count is None else f"{report.estimated_point_count:,}"
    lines = [
        "Polygon Batch Preflight",
        f"Ready: {'YES' if report.ready else 'NO'}",
        f"LiDAR folder: {report.request.lidar_folder}",
        f"Polygon source: {report.request.polygon.source_description}",
        f"Polygon CRS: {report.request.polygon.source_crs}",
        f"Processing CRS: {report.request.polygon.processing_crs}",
        f"Polygon area: {report.request.polygon.area:g} square map units",
        f"Discovered sources: {len(report.inventory.sources)}",
        f"Intersecting sources: {len(report.selected_sources)}",
        f"Skipped sources: {len(report.skipped_sources)}",
        f"Estimated points: {point_text}",
        f"Estimated source bytes: {report.estimated_source_bytes:,}",
        "Products: " + ", ".join(product.value for product in report.request.products),
        f"Output folder: {report.request.output_folder}",
        f"Manifest: {report.manifest_path}",
        "",
        "Blockers:",
        *(f"- {item}" for item in report.blockers),
    ]
    if not report.blockers:
        lines.append("- None")
    lines.extend(("", "Warnings:"))
    lines.extend(f"- {item}" for item in report.warnings)
    if not report.warnings:
        lines.append("- None")
    lines.extend(("", "Intersecting sources:"))
    lines.extend(f"- {source.path} ({source.source_type})" for source in report.selected_sources[:50])
    if len(report.selected_sources) > 50:
        lines.append(f"- {len(report.selected_sources) - 50} additional source(s)")
    return "\n".join(lines)


def execute_polygon_batch(
    report: PolygonBatchPreflightReport,
    adapter: PyForestScanAdapter | None = None,
    executor: BatchExecutor | None = None,
    item_callback=None,
    job_callback=None,
    control_callback=None,
) -> BatchResult:
    """Clip intersecting sources to the polygon, then execute the normal Batch runner."""
    if report.blockers:
        raise ValueError("Polygon batch preflight blockers must be resolved before execution.")
    adapter = adapter or PyForestScanAdapter()
    batch_folder = report.batch_folder if report.batch_folder.exists() else create_batch_folder(report.request.output_folder)
    clipped_folder = batch_folder / "polygon_clipped_sources"
    clipped_folder.mkdir(parents=True, exist_ok=True)
    clipped_sources: list[Path] = []
    clip_records: list[dict[str, str]] = []
    for source in report.selected_sources:
        output = clipped_folder / f"{_safe_stem(source.path)}_polygon_clip.laz"
        bounds = report.request.polygon.bounds.to_ept_bounds() if source.source_type == "ept" else None
        result = adapter.normalize_heights(
            HagNormalizationRequest(
                input_path=source.path,
                crs=report.request.polygon.processing_crs,
                output_path=output,
                reproject=bool(source.crs and source.crs != report.request.polygon.processing_crs),
                bounds=bounds,
                crop_polygon=report.request.polygon.geometry_wkt,
                compress=True,
            )
        )
        if result.output_path is not None:
            clipped_sources.append(Path(result.output_path))
            clip_records.append({"source": str(source.path), "clipped": str(result.output_path), "points": str(result.point_count or "unknown")})
    if not clipped_sources:
        raise ValueError("Polygon clipping produced no runnable clipped sources.")
    batch_request = BatchRequest(
        input_folder=report.request.lidar_folder,
        output_folder=report.request.output_folder,
        recursive=report.request.recursive,
        datasets=tuple(clipped_sources),
        settings=report.request.settings,
        title=report.request.title,
        batch_folder=batch_folder,
    )
    write_polygon_batch_manifest(report, clip_records, batch_folder=batch_folder)
    runner = executor or BatchExecutor()
    return runner.run(batch_request, item_callback=item_callback, job_callback=job_callback, control_callback=control_callback)


def write_polygon_batch_manifest(report: PolygonBatchPreflightReport, clip_records: list[dict[str, str]] | None = None, *, batch_folder: Path | None = None) -> Path:
    """Write polygon-specific metadata beside the normal batch manifest."""
    folder = batch_folder or report.batch_folder
    path = folder / POLYGON_MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "polygon_area_processing",
        "lidar_folder": str(report.request.lidar_folder),
        "output_folder": str(report.request.output_folder),
        "polygon": {
            "source_description": report.request.polygon.source_description,
            "source_crs": report.request.polygon.source_crs,
            "processing_crs": report.request.polygon.processing_crs,
            "geometry_type": report.request.polygon.geometry_type,
            "feature_count": report.request.polygon.feature_count,
            "bounds": report.request.polygon.bounds.__dict__,
            "area": report.request.polygon.area,
            "wkt": report.request.polygon.geometry_wkt,
            "warnings": list(report.request.polygon.warnings),
        },
        "sources": [
            {
                "path": str(source.path),
                "source_type": source.source_type,
                "crs": source.crs,
                "point_count": source.point_count,
                "bounds": None if source.bounds is None else source.bounds.__dict__,
                "size_bytes": source.size_bytes,
                "modified_ns": source.modified_ns,
            }
            for source in report.selected_sources
        ],
        "skipped_sources": [str(source.path) for source in report.skipped_sources],
        "blockers": list(report.blockers),
        "warnings": list(report.warnings),
        "clip_records": clip_records or [],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def selected_source_paths(report: PolygonBatchPreflightReport) -> tuple[Path, ...]:
    """Return intersecting source paths for tests and UI summaries."""
    return tuple(source.path for source in report.selected_sources)


def _estimated_points(sources: tuple[LidarSourceRecord, ...]) -> int | None:
    counts = [source.point_count for source in sources]
    if not counts or any(count is None for count in counts):
        return None
    return int(sum(count for count in counts if count is not None))


def _planned_polygon_batch_folder(output_folder: Path) -> Path:
    return Path(output_folder) / "pyforestscan_polygon_batch_planned"


def _safe_stem(path: Path) -> str:
    stem = path.parent.name if path.name.lower() == "ept.json" else path.stem
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "source"
