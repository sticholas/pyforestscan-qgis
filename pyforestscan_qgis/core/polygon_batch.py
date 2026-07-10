"""Polygon area batch preflight and execution helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .adapter import PyForestScanAdapter
from .batch import BatchProductSettings, BatchRequest, BatchResult, create_batch_folder
from .batch_executor import BatchExecutor
from .lidar_catalog import catalog_summary
from .lidar_catalog_models import CatalogThresholds, LidarCatalogQueryResult, PolygonQueryGeometry, default_lidar_catalog_path
from .lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from .lidar_inventory import LidarInventory, LidarSourceRecord
from .polygon_processing import PolygonProcessingPlan, build_polygon_processing_plan
from .polygon_source import NormalizedPolygonSelection
from .raster_mask import RasterMaskResult, apply_polygon_mask_to_outputs
from .types import HagNormalizationRequest, ProductType

POLYGON_MANIFEST_NAME = "polygon_batch_manifest.json"
DEFAULT_POLYGON_SOURCE_WARNING = 25
DEFAULT_POLYGON_POINT_WARNING = 25_000_000
DEFAULT_POLYGON_SIZE_WARNING_BYTES = 20 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class PolygonBatchRequest:
    """Request to run Batch from a repository clipped by one polygon."""

    lidar_folder: Path
    output_folder: Path
    polygon: NormalizedPolygonSelection
    products: tuple[ProductType, ...]
    settings: BatchProductSettings
    recursive: bool = True
    batch_folder: Path | None = None
    title: str = "PyForestScan Polygon Batch"
    catalog_path: Path | None = None
    catalog_crs: str | None = None
    thresholds: CatalogThresholds = CatalogThresholds()


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
    catalog_path: Path
    query_geometry: PolygonQueryGeometry
    query_result: LidarCatalogQueryResult | None = None
    catalog_skipped_count: int = 0

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def run_polygon_batch_preflight(request: PolygonBatchRequest) -> PolygonBatchPreflightReport:
    """Query the spatial catalog, intersect sources with the polygon, and assess readiness."""
    catalog_path = request.catalog_path or default_lidar_catalog_path(request.lidar_folder)
    query_geometry = derive_polygon_query_geometry(request.polygon, catalog_crs=request.catalog_crs)
    batch_folder = request.batch_folder or _planned_polygon_batch_folder(request.output_folder)
    manifest_path = batch_folder / POLYGON_MANIFEST_NAME
    empty_inventory = LidarInventory(request.lidar_folder, ())
    blockers: list[str] = []
    warnings: list[str] = list(query_geometry.warnings)
    if not request.products:
        blockers.append("Select at least one product.")
    if not Path(request.lidar_folder).is_dir():
        blockers.append(f"LiDAR repository does not exist: {request.lidar_folder}")
    if not Path(catalog_path).exists():
        blockers.append("Build a LiDAR catalog before running Polygon Area Processing. Normal preflight does not recursively scan the repository.")
        plan = _empty_plan(empty_inventory, request, query_geometry, warnings)
        return PolygonBatchPreflightReport(
            request=request,
            inventory=empty_inventory,
            plan=plan,
            ready=False,
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=tuple(dict.fromkeys(warnings)),
            selected_sources=(),
            skipped_sources=(),
            estimated_point_count=None,
            estimated_source_bytes=0,
            batch_folder=batch_folder,
            manifest_path=manifest_path,
            catalog_path=Path(catalog_path),
            query_geometry=query_geometry,
            query_result=None,
            catalog_skipped_count=0,
        )
    query = query_catalog_for_polygon(
        catalog_path,
        request.lidar_folder,
        request.polygon,
        catalog_crs=request.catalog_crs,
        thresholds=request.thresholds,
    )
    selected = query.source_records
    inventory = LidarInventory(request.lidar_folder, selected, cache_path=Path(catalog_path))
    try:
        plan = build_polygon_processing_plan(
            inventory,
            request.polygon.to_polygon_selection(),
            request.output_folder,
            tuple(product.value for product in request.products),
            processing_crs=request.polygon.processing_crs,
        )
    except ValueError as exc:
        blockers.append(str(exc))
        plan = _empty_plan(inventory, request, query_geometry, warnings)
    warnings.extend(query.warnings)
    warnings.extend(plan.warnings)
    if not selected:
        blockers.append("No cataloged LiDAR sources intersect the selected polygon envelope.")
    if query.metadata_error_count:
        warnings.append(f"{query.metadata_error_count:,} catalog source(s) have metadata errors; polygon selection may be incomplete until they are retried.")
    point_count = query.estimated_point_count
    source_bytes = query.estimated_bytes
    if len(selected) >= DEFAULT_POLYGON_SOURCE_WARNING:
        warnings.append("Large polygon batch: many intersecting sources selected.")
    if point_count is not None and point_count >= DEFAULT_POLYGON_POINT_WARNING:
        warnings.append("Large polygon batch: estimated point count is high; run sequentially unless carefully tested.")
    if source_bytes >= DEFAULT_POLYGON_SIZE_WARNING_BYTES:
        warnings.append("Large polygon batch: source file size is high; ensure disk and memory headroom.")
    return PolygonBatchPreflightReport(
        request=request,
        inventory=inventory,
        plan=plan,
        ready=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        selected_sources=selected,
        skipped_sources=(),
        estimated_point_count=point_count,
        estimated_source_bytes=source_bytes,
        batch_folder=batch_folder,
        manifest_path=manifest_path,
        catalog_path=Path(catalog_path),
        query_geometry=query_geometry,
        query_result=query,
        catalog_skipped_count=query.skipped_count,
    )


def polygon_preflight_text(report: PolygonBatchPreflightReport) -> str:
    """Format a concise Batch-page polygon preflight report."""
    point_text = "unknown" if report.estimated_point_count is None else f"{report.estimated_point_count:,}"
    query = report.query_result
    lines = [
        "Polygon Batch Preflight",
        f"Ready: {'YES' if report.ready else 'NO'}",
        f"LiDAR repository: {report.request.lidar_folder}",
        f"Catalog: {report.catalog_path}",
        f"Polygon source: {report.request.polygon.source_description}",
        f"Polygon CRS: {report.request.polygon.source_crs}",
        f"Processing CRS: {report.request.polygon.processing_crs}",
        f"Catalog envelope: {report.query_geometry.envelope.xmin:g}, {report.query_geometry.envelope.ymin:g}, {report.query_geometry.envelope.xmax:g}, {report.query_geometry.envelope.ymax:g}",
        f"EPT bounds: {report.query_geometry.ept_bounds}",
        f"Exact polygon area: {report.request.polygon.area:g} square map units",
        f"Catalog query time: {0.0 if query is None else query.query_seconds:.4f} seconds",
        f"Catalog candidates: {0 if query is None else query.candidate_count}",
        f"Intersecting sources: {len(report.selected_sources)}",
        f"Skipped catalog sources: {report.catalog_skipped_count}",
        f"Metadata errors: {0 if query is None else query.metadata_error_count}",
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
    """Clip intersecting sources to the exact polygon, then execute the normal Batch runner."""
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
        bounds = report.query_geometry.ept_bounds if source.source_type == "ept" else None
        result = adapter.normalize_heights(
            HagNormalizationRequest(
                input_path=source.path,
                crs=report.query_geometry.catalog_crs or report.request.polygon.processing_crs,
                output_path=output,
                reproject=bool(source.crs and source.crs != report.request.polygon.processing_crs),
                bounds=bounds,
                crop_polygon=report.query_geometry.exact_polygon_wkt,
                compress=True,
            )
        )
        if result.output_path is not None:
            clipped_sources.append(Path(result.output_path))
            clip_records.append({"source": str(source.path), "clipped": str(result.output_path), "points": str(result.point_count or "unknown"), "bounds_used": str(bounds)})
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
    result = runner.run(batch_request, item_callback=item_callback, job_callback=job_callback, control_callback=control_callback)
    mask_results = _mask_result_outputs(result, report)
    write_polygon_batch_manifest(report, clip_records, batch_folder=batch_folder, mask_records=[item.__dict__ | {"path": str(item.path)} for item in mask_results])
    return result


def write_polygon_batch_manifest(
    report: PolygonBatchPreflightReport,
    clip_records: list[dict[str, str]] | None = None,
    *,
    batch_folder: Path | None = None,
    mask_records: list[dict[str, str]] | None = None,
) -> Path:
    """Write polygon-specific metadata beside the normal batch manifest."""
    folder = batch_folder or report.batch_folder
    path = folder / POLYGON_MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    query = report.query_result
    payload = {
        "mode": "polygon_area_processing",
        "lidar_repository": str(report.request.lidar_folder),
        "catalog_path": str(report.catalog_path),
        "output_folder": str(report.request.output_folder),
        "query": {
            "envelope": report.query_geometry.envelope.__dict__,
            "ept_bounds": report.query_geometry.ept_bounds,
            "query_seconds": None if query is None else query.query_seconds,
            "candidate_count": None if query is None else query.candidate_count,
            "exact_intersecting_count": None if query is None else query.exact_intersecting_count,
            "skipped_count": report.catalog_skipped_count,
            "metadata_error_count": None if query is None else query.metadata_error_count,
        },
        "polygon": {
            "source_description": report.request.polygon.source_description,
            "source_crs": report.request.polygon.source_crs,
            "processing_crs": report.request.polygon.processing_crs,
            "geometry_type": report.request.polygon.geometry_type,
            "feature_count": report.request.polygon.feature_count,
            "bounds": report.request.polygon.bounds.__dict__,
            "area": report.request.polygon.area,
            "wkt": report.request.polygon.geometry_wkt,
            "exact_query_wkt": report.query_geometry.exact_polygon_wkt,
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
        "blockers": list(report.blockers),
        "warnings": list(report.warnings),
        "clip_records": clip_records or [],
        "mask_records": mask_records or [],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def selected_source_paths(report: PolygonBatchPreflightReport) -> tuple[Path, ...]:
    """Return intersecting source paths for tests and UI summaries."""
    return tuple(source.path for source in report.selected_sources)


def catalog_status_text(lidar_folder: Path | str, catalog_path: Path | str | None = None) -> str:
    """Return compact catalog status text for Mission Control."""
    path = Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(lidar_folder)
    summary = catalog_summary(path, lidar_folder)
    if not summary.exists:
        return f"No Catalog - build catalog at {path}"
    return (
        f"Catalog Ready - {summary.indexed_count:,} indexed source(s), "
        f"{summary.error_count:,} error(s), root {summary.root_path}, updated {summary.last_indexed_at or 'unknown'}"
    )


def _empty_plan(inventory: LidarInventory, request: PolygonBatchRequest, query_geometry: PolygonQueryGeometry, warnings: list[str]) -> PolygonProcessingPlan:
    return PolygonProcessingPlan(
        inventory=inventory,
        polygon=request.polygon.to_polygon_selection(),
        output_folder=request.output_folder,
        products=tuple(product.value for product in request.products),
        intersections=(),
        processing_crs=request.polygon.processing_crs,
        warnings=tuple(warnings),
    )


def _mask_result_outputs(result: BatchResult, report: PolygonBatchPreflightReport) -> tuple[RasterMaskResult, ...]:
    paths: list[Path] = []
    for item in result.items:
        paths.extend(Path(output) for output in item.outputs)
    return apply_polygon_mask_to_outputs(
        paths,
        report.query_geometry.exact_polygon_wkt,
        polygon_crs=report.request.polygon.source_crs,
        processing_crs=report.request.polygon.processing_crs,
    )


def _planned_polygon_batch_folder(output_folder: Path) -> Path:
    return Path(output_folder) / "pyforestscan_polygon_batch_planned"


def _safe_stem(path: Path) -> str:
    stem = path.parent.name if path.name.lower() == "ept.json" else path.stem
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "source"
