"""Polygon area batch preflight and execution helpers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchItemResult, BatchProductSettings, BatchRequest, BatchResult, batch_run_context, create_batch_folder
from .batch_results import write_batch_summaries
from .batch_executor import BatchExecutor
from .ept_bounds import EptBounds
from .ept_repository import incorrect_ept_catalog_detected
from .lidar_catalog import catalog_summary
from .lidar_catalog_models import CatalogThresholds, LidarCatalogQueryResult, PolygonQueryGeometry, default_lidar_catalog_path
from .lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from .lidar_inventory import LidarInventory, LidarSourceRecord
from .polygon_processing import PolygonProcessingPlan, build_polygon_processing_plan
from .polygon_source import NormalizedPolygonSelection
from .polygon_transport import polygon_execution_input_from_selection, unique_polygon_job_id
from .raster_mask import RasterMaskResult, apply_polygon_mask_to_outputs
from .types import CanopyCoverRequest, ChmRequest, DtmRequest, FhdRequest, HagNormalizationRequest, PadRequest, PaiRequest, PointDensityRequest, ProductType, RumpleRequest, VoxelStatRequest

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
    execution_backend: str = "PBM"
    backend_ready: bool = False
    backend_message: str = "Backend readiness was not checked."
    spatial_alignment_status: str = "Ready"

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def run_polygon_batch_preflight(request: PolygonBatchRequest, *, backend_probe: Callable[[], tuple[bool, str]] | None = None) -> PolygonBatchPreflightReport:
    """Query the spatial catalog, intersect sources with the polygon, and assess readiness."""
    catalog_path = request.catalog_path or default_lidar_catalog_path(request.lidar_folder)
    query_geometry = derive_polygon_query_geometry(request.polygon, catalog_crs=request.catalog_crs)
    batch_folder = request.batch_folder or _planned_polygon_batch_folder(request.output_folder)
    manifest_path = batch_folder / POLYGON_MANIFEST_NAME
    empty_inventory = LidarInventory(request.lidar_folder, ())
    blockers: list[str] = []
    warnings: list[str] = list(query_geometry.warnings)
    backend_ready, backend_message = _probe_pbm_backend(backend_probe)
    if not backend_ready:
        blockers.append("Managed processing backend cannot import PyForestScan. Repair or rebuild the backend from Environment.")
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
            backend_ready=backend_ready,
            backend_message=backend_message,
        )
    if incorrect_ept_catalog_detected(catalog_path, request.lidar_folder):
        blockers.append("Incorrect EPT Catalog Detected. Repair EPT Catalog before running; internal EPT node files should be one logical EPT dataset.")
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
        backend_ready=backend_ready,
        backend_message=backend_message,
    )


def polygon_preflight_text(report: PolygonBatchPreflightReport) -> str:
    """Format a concise Batch-page polygon preflight report."""
    query = report.query_result
    repository_type = "EPT dataset" if _is_logical_spatial_report(report) and report.selected_sources[0].source_type == "ept" else "LiDAR repository"
    estimate_text = _readable_point_estimate(report.estimated_point_count, None if query is None else query.point_estimate_confidence)
    workload = _workload_label(report.estimated_point_count, report.estimated_source_bytes)
    timing = getattr(query, "timing_seconds", {}) if query is not None else {}
    lines = [
        "Polygon Preflight",
        f"Ready: {'YES' if report.ready else 'NO'}",
        f"Repository: {repository_type}",
        f"Logical inputs: {len(report.selected_sources)}",
        f"Polygon area: {_format_area_hectares(report.request.polygon.area)}",
        "Products: " + ", ".join(product.value for product in report.request.products),
        f"Backend: PBM {'Ready' if report.backend_ready else 'Not Ready'}",
        f"Spatial alignment: {report.spatial_alignment_status}",
        f"Estimated workload: {workload}",
        f"Estimated points: {estimate_text}",
        f"Output: {report.request.output_folder}",
        f"Warnings: {len(report.warnings)}",
        "",
        "Blockers:",
    ]
    lines.extend(f"- {item}" for item in report.blockers)
    if not report.blockers:
        lines.append("- None")
    lines.extend(("", "Warnings:"))
    lines.extend(f"- {item}" for item in report.warnings)
    if not report.warnings:
        lines.append("- None")
    lines.extend(("", "Source details:"))
    if _is_logical_spatial_report(report):
        lines.extend(f"- {source.path} ({source.source_type})" for source in report.selected_sources)
    else:
        lines.extend(f"- {source.path} ({source.source_type})" for source in report.selected_sources[:10])
        if len(report.selected_sources) > 10:
            lines.append(f"- {len(report.selected_sources) - 10} additional file(s)")
    lines.extend(("", "Technical diagnostics:"))
    if query is None:
        lines.append("- Catalog query was not run.")
    else:
        lines.append(f"- RTree lookup: {timing.get('rtree_lookup', query.query_seconds):.4f} s")
        lines.append(f"- Row loading: {timing.get('row_loading', 0.0):.4f} s")
        lines.append(f"- Workload estimation: {timing.get('workload_estimation', 0.0):.4f} s")
        lines.append(f"- Total preflight query work: {query.query_seconds:.4f} s")
        lines.append(f"- Catalog candidates: {query.candidate_count}")
        lines.append(f"- Skipped catalog sources: {report.catalog_skipped_count}")
        lines.append(f"- Metadata errors: {query.metadata_error_count}")
    lines.append(f"- Backend check: {report.backend_message}")
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
    if _is_logical_spatial_report(report):
        return _execute_logical_spatial_batch(report, adapter, batch_folder, item_callback=item_callback)
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
            "ept_bounds": EptBounds.from_value(report.query_geometry.ept_bounds, crs=report.query_geometry.catalog_crs).to_json(),
            "pdal_bounds_expression": EptBounds.from_value(report.query_geometry.ept_bounds, crs=report.query_geometry.catalog_crs).to_pdal_range_string(),
            "bounds_query_crs": report.query_geometry.catalog_crs,
            "spatial_alignment": report.spatial_alignment_status,
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
            "polygon_original_crs": report.request.polygon.source_crs,
            "ept_source_crs": report.query_geometry.catalog_crs,
            "bounds_query_crs": report.query_geometry.catalog_crs,
            "clipping_geometry_crs": report.query_geometry.catalog_crs,
            "output_crs": report.request.polygon.processing_crs,
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



def _probe_pbm_backend(probe: Callable[[], tuple[bool, str]] | None) -> tuple[bool, str]:
    if probe is not None:
        try:
            ready, message = probe()
            return bool(ready), str(message)
        except Exception as exc:  # noqa: BLE001 - preflight should explain probe failure.
            return False, f"PBM backend check failed: {exc}"
    try:
        from .backend import BackendService

        availability = BackendService().can_execute_processing()
        return bool(availability.ready), availability.message
    except Exception as exc:  # noqa: BLE001
        return False, f"PBM backend check failed: {exc}"


def _is_logical_spatial_report(report: PolygonBatchPreflightReport) -> bool:
    return bool(report.selected_sources) and all(source.source_type in {"ept", "copc"} for source in report.selected_sources)


def _execute_logical_spatial_batch(report: PolygonBatchPreflightReport, adapter: PyForestScanAdapter, batch_folder: Path, *, item_callback=None) -> BatchResult:
    started_at = datetime.now(timezone.utc).isoformat()
    source = report.selected_sources[0]
    job_folder = batch_folder / "polygon_jobs" / unique_polygon_job_id(source.source_type)
    context = batch_run_context(Path(source.path), job_folder, reuse_existing=True).ensure_directories()
    for child in ("inputs", "staging", "outputs", "logs", "diagnostics"):
        (job_folder / child).mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    stages = _polygon_progress_stages(report.request.products)
    try:
        _emit_polygon_stage(item_callback, source, context, "Preparing Inputs", "Preparing durable polygon job workspace.")
        write_polygon_batch_manifest(report, [{"source": str(source.path), "clipped": "native", "points": str(source.point_count or "unknown"), "bounds_used": str(report.query_geometry.ept_bounds), "job_folder": str(job_folder)}], batch_folder=batch_folder)
        for product in report.request.products:
            _emit_polygon_stage(item_callback, source, context, "Generating Product", f"Generating {product.value}.")
            result_path = _logical_product_output_path(context.outputs_dir, product)
            request = _logical_product_request(product, source.path, result_path, report)
            result = _run_logical_product(adapter, product, request)
            outputs.append(Path(getattr(result, "output_path")))
        item = BatchItemResult(Path(source.path), context, "completed", "Logical EPT/COPC source processed through PBM backend.", tuple(outputs), _requested_extent_summary(report))
    except Exception as exc:  # noqa: BLE001
        item = BatchItemResult(Path(source.path), context, "failed", _friendly_polygon_execution_error(str(exc)), tuple(outputs), _requested_extent_summary(report))
    finished_at = datetime.now(timezone.utc).isoformat()
    result = BatchResult("polygon-logical", report.request.title, started_at, finished_at, batch_folder, (item,), batch_folder / "batch_summary.json", batch_folder / "batch_summary.csv", batch_folder / "batch_summary.html")
    write_polygon_batch_manifest(report, [{"source": str(source.path), "clipped": "native", "points": str(source.point_count or "unknown"), "bounds_used": str(report.query_geometry.ept_bounds), "job_folder": str(context.run_folder)}], batch_folder=batch_folder)
    if item_callback is not None:
        item_callback(item)
    return write_batch_summaries(result)


def _logical_product_request(product: ProductType, input_path: Path, output_path: Path, report: PolygonBatchPreflightReport):
    kwargs = {
        "input_path": input_path,
        "output_path": output_path,
        "crs": report.query_geometry.catalog_crs or report.request.polygon.processing_crs,
        "bounds": EptBounds.from_value(report.query_geometry.ept_bounds, crs=report.query_geometry.catalog_crs).to_json(),
        "crop_polygon": report.query_geometry.exact_polygon_wkt,
        "polygon_execution_input": polygon_execution_input_from_selection(report.request.polygon, transformed_wkt=report.query_geometry.exact_polygon_wkt),
    }
    settings = report.request.settings
    if product == ProductType.CHM:
        return ChmRequest(grid_resolution=settings.grid_resolution, interpolation=settings.chm_interpolation, interp_valid_region=settings.chm_interpolate_valid_region, interp_clean_edges=settings.chm_clean_edges, **kwargs)
    if product == ProductType.PAD:
        return PadRequest(grid_resolution=settings.grid_resolution, voxel_height=settings.height_bin_size or 1.0, **kwargs)
    if product == ProductType.PAI:
        return PaiRequest(grid_resolution=settings.grid_resolution, voxel_height=settings.height_bin_size or 1.0, **kwargs)
    if product == ProductType.FHD:
        return FhdRequest(grid_resolution=settings.grid_resolution, voxel_height=settings.height_bin_size or 1.0, **kwargs)
    if product == ProductType.RUMPLE:
        return RumpleRequest(grid_resolution=settings.grid_resolution, interpolation=settings.chm_interpolation, interp_valid_region=settings.chm_interpolate_valid_region, interp_clean_edges=settings.chm_clean_edges, **kwargs)
    if product == ProductType.CANOPY_COVER:
        return CanopyCoverRequest(grid_resolution=settings.grid_resolution, canopy_height_threshold=settings.canopy_cover_height_threshold, voxel_height=settings.height_bin_size or 1.0, **kwargs)
    if product == ProductType.DTM:
        return DtmRequest(resolution=settings.grid_resolution, **kwargs)
    if product == ProductType.POINT_DENSITY:
        return PointDensityRequest(grid_resolution=settings.grid_resolution, voxel_height=settings.height_bin_size or 1.0, **kwargs)
    if product == ProductType.VOXEL_STAT:
        return VoxelStatRequest(grid_resolution=settings.grid_resolution, voxel_height=settings.height_bin_size or 1.0, dimension="HeightAboveGround", stat="count", **kwargs)
    raise ValueError(f"Unsupported polygon product for logical EPT/COPC execution: {product.value}")


def _run_logical_product(adapter: PyForestScanAdapter, product: ProductType, request):
    method_names = {
        ProductType.CHM: "create_chm",
        ProductType.PAD: "create_pad",
        ProductType.PAI: "create_pai",
        ProductType.FHD: "create_fhd",
        ProductType.RUMPLE: "create_rumple",
        ProductType.CANOPY_COVER: "create_canopy_cover",
        ProductType.DTM: "generate_dtm",
        ProductType.POINT_DENSITY: "create_point_density",
        ProductType.VOXEL_STAT: "create_voxel_stat",
    }
    return getattr(adapter, method_names[product])(request)


def _emit_polygon_stage(item_callback, source: LidarSourceRecord, context, stage: str, message: str) -> None:
    if item_callback is not None:
        item_callback(BatchItemResult(Path(source.path), context, "running", f"{stage}: {message}", (), stage))


def _polygon_progress_stages(products: tuple[ProductType, ...]) -> tuple[str, ...]:
    product_labels = tuple(product.value for product in products)
    return (
        "Preparing Inputs",
        "Validating Geometry",
        "Preparing Spatial Read",
        "Applying EPT Bounds",
        "Reading Point Cloud",
        "Normalizing Heights",
        "Generating Product: " + ", ".join(product_labels),
        "Writing Raster",
        "Masking Output",
        "Writing Metadata",
        "Finalizing",
        "Completed",
    )


def _logical_product_output_path(folder: Path, product: ProductType) -> Path:
    names = {
        ProductType.CHM: "chm.tif",
        ProductType.PAD: "pad.tif",
        ProductType.PAI: "pai.tif",
        ProductType.FHD: "fhd.tif",
        ProductType.RUMPLE: "rumple_summary.csv",
        ProductType.CANOPY_COVER: "canopy_cover.tif",
        ProductType.DTM: "dtm.tif",
        ProductType.POINT_DENSITY: "point_density.tif",
        ProductType.VOXEL_STAT: "voxel_statistic.tif",
    }
    return folder / names[product]


def _friendly_polygon_execution_error(message: str) -> str:
    if "pyforestscan.handlers" in message or "Required dependency is not importable" in message:
        return "Polygon processing could not start because the managed backend is missing PyForestScan or is not being used correctly. Open Environment, check the Backend, or view technical details."
    return message


def _readable_point_estimate(value: int | None, confidence: str | None) -> str:
    if value is None:
        return "Not available for this repository"
    label = confidence or "Approximate"
    if value >= 1_000_000_000:
        amount = f"{value / 1_000_000_000:.1f} billion"
    elif value >= 1_000_000:
        amount = f"{value / 1_000_000:.1f} million"
    else:
        amount = f"{value:,}"
    return f"Approximately {amount} points ({label})"


def _workload_label(points: int | None, source_bytes: int) -> str:
    if points is None:
        return "Unknown"
    if points >= 100_000_000 or source_bytes >= DEFAULT_POLYGON_SIZE_WARNING_BYTES:
        return "Large"
    if points >= 5_000_000:
        return "Moderate"
    return "Small"


def _format_area_hectares(area: float) -> str:
    if area <= 0:
        return "Unknown"
    return f"{area / 10000.0:.1f} ha"


def _requested_extent_summary(report: PolygonBatchPreflightReport) -> str:
    bounds = report.query_geometry.ept_bounds
    area_ha = report.request.polygon.area / 10000.0 if report.request.polygon.area else 0.0
    return f"Requested area {area_ha:.1f} ha; Read extent polygon envelope X {bounds[0][0]:.3f} to {bounds[0][1]:.3f}; Y {bounds[1][0]:.3f} to {bounds[1][1]:.3f}"


def _source_bounds_summary(source: LidarSourceRecord) -> str:
    if source.bounds is None:
        return "Unavailable"
    return f"X {source.bounds.xmin:.3f} to {source.bounds.xmax:.3f}; Y {source.bounds.ymin:.3f} to {source.bounds.ymax:.3f}"

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
