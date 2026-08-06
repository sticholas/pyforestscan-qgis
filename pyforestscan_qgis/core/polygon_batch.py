"""Polygon area batch preflight and execution helpers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .adapter import PyForestScanAdapter
from .batch import BatchItemResult, BatchProductSettings, BatchRequest, BatchResult, batch_run_context, create_batch_folder
from .batch_options import BatchExecutionOptions, PolygonBatchOptions, polygon_option_applicability, requested_effective_concurrency
from .batch_results import write_batch_summaries
from .batch_executor import BatchExecutor
from .ept_bounds import EptBounds
from .ept_repository import incorrect_ept_catalog_detected
from .direct_lidar_selection import DirectLidarFolderSelector, PolygonLidarSelectionResult, SelectionMethodComparison, compare_selection_methods
from .lidar_catalog import catalog_summary
from .lidar_catalog_models import CatalogThresholds, LidarCatalogQueryResult, PolygonQueryGeometry, default_lidar_catalog_path
from .spatial_selection import Bounds2D
from .lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from .polygon_source_selection import PolygonExecutionPlan, PolygonSourceSelectionResult, PolygonSourceSelectionService, build_polygon_execution_plan
from .lidar_inventory import LidarInventory, LidarSourceRecord
from .polygon_processing import PolygonProcessingPlan, build_polygon_processing_plan
from .polygon_source import NormalizedPolygonSelection
from .polygon_transport import polygon_execution_input_from_selection, unique_polygon_job_id
from .raster_mask import RasterMaskOptions, RasterMaskResult, apply_polygon_mask_to_outputs, is_maskable_raster
from .output_registry import generated_output_for_path, write_output_registry
from .polygon_lidar_processing import selected_path_invariant
from .source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent
from .work_unit_scheduler import CheckpointStore, PolygonProductWorkScheduler, WorkUnitResult
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
    shared_execution_options: BatchExecutionOptions | None = None
    polygon_options: PolygonBatchOptions = PolygonBatchOptions()
    selection_mode: str = "automatic"
    direct_header_fallback: bool = True
    repository_crs_override: str | None = None


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
    repository: object | None = None
    source_selection: PolygonSourceSelectionResult | None = None
    execution_plan: PolygonExecutionPlan | None = None
    structured_warnings: tuple[object, ...] = ()
    structured_blockers: tuple[object, ...] = ()
    plan_signature: str = ""
    selection_method: str = "catalog"
    direct_selection: PolygonLidarSelectionResult | None = None
    selection_comparison: SelectionMethodComparison | None = None

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def run_polygon_batch_preflight(request: PolygonBatchRequest, *, backend_probe: Callable[[], tuple[bool, str]] | None = None) -> PolygonBatchPreflightReport:
    """Resolve repository identity, select sources, and build one execution plan."""
    service = PolygonSourceSelectionService()
    repository = service.resolve_repository(request.lidar_folder, request.catalog_path)
    catalog_path = repository.catalog_path or request.catalog_path or default_lidar_catalog_path(repository.normalized_path)
    query_geometry = derive_polygon_query_geometry(request.polygon, catalog_crs=repository.source_crs or request.catalog_crs)
    batch_folder = request.batch_folder or _planned_polygon_batch_folder(request.output_folder)
    manifest_path = batch_folder / POLYGON_MANIFEST_NAME
    empty_inventory = LidarInventory(repository.normalized_path, ())
    blockers: list[str] = []
    warnings: list[str] = list(query_geometry.warnings)
    backend_ready, backend_message = _probe_pbm_backend(backend_probe)
    if not backend_ready:
        blockers.append("Managed processing backend cannot import PyForestScan. Repair or rebuild the backend from Environment.")
    if not request.products:
        blockers.append("Select at least one product.")
    if not Path(repository.normalized_path).is_dir():
        blockers.append(f"LiDAR repository does not exist: {repository.normalized_path}")
    if repository.repository_kind != "ept" and (request.selection_mode == "direct_header_scan" or (request.direct_header_fallback and not Path(catalog_path).exists())):
        direct = DirectLidarFolderSelector().select(repository.normalized_path, request.polygon, repository_crs_override=request.repository_crs_override or repository.source_crs, recursive=request.recursive)
        return _report_from_direct_selection(request, repository, service, query_geometry, batch_folder, manifest_path, direct, backend_ready, backend_message, catalog_path)
    if repository.repository_kind != "ept" and not Path(catalog_path).exists():
        blockers.append("Build a LiDAR catalog before running Polygon Area Processing, or use Direct Header Scan.")
        plan = _empty_plan(empty_inventory, request, query_geometry, warnings)
        execution_plan = build_polygon_execution_plan(
            repository=repository,
            polygon_context=service.last_polygon_context or _fallback_polygon_context(request.polygon, query_geometry),
            source_selection=PolygonSourceSelectionResult(
                repository_kind=repository.repository_kind,
                logical_candidates=(),
                selected_sources=(),
                rejected_sources=(),
                transformed_polygon=query_geometry.exact_polygon_wkt,
                transformed_envelope=__import__("pyforestscan_qgis.core.polygon_source_selection", fromlist=["SpatialEnvelope"]).SpatialEnvelope.from_bounds(query_geometry.envelope, query_geometry.catalog_crs),
                source_extent=None,
                overlap_result="not-run",
                exact_intersection_result="not-run",
                warnings=(),
                blockers=(),
                timings={},
            ),
            products=tuple(product.value for product in request.products),
            shared_batch_options=request.shared_execution_options or BatchExecutionOptions.from_batch_settings(request.settings),
            polygon_batch_options=request.polygon_options,
            requested_concurrency=request.shared_execution_options.maximum_parallel_jobs if request.shared_execution_options else BatchExecutionOptions.from_batch_settings(request.settings).maximum_parallel_jobs,
            effective_concurrency=1,
            output_folder=request.output_folder,
            backend_ready=backend_ready,
            backend_message=backend_message,
        )
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
            repository=repository,
            execution_plan=execution_plan,
            plan_signature=execution_plan.plan_signature,
        )
    if repository.repository_kind == "ept" and Path(catalog_path).exists() and incorrect_ept_catalog_detected(catalog_path, repository.normalized_path):
        blockers.append("Incorrect EPT Catalog Detected. Repair EPT Catalog before running; internal EPT node files should be one logical EPT dataset.")
    selection = service.select_sources(repository, request.polygon, catalog_crs=request.catalog_crs, thresholds=request.thresholds)
    if repository.repository_kind == "ept":
        query_geometry = PolygonQueryGeometry(
            envelope=selection.transformed_envelope.to_bounds(),
            exact_polygon_wkt=selection.transformed_polygon,
            source_crs=request.polygon.processing_crs or request.polygon.source_crs,
            catalog_crs=selection.transformed_envelope.crs,
            ept_bounds=selection.transformed_envelope.to_bounds().to_ept_bounds(),
            warnings=tuple(message.to_text() for message in selection.warnings),
        )
    query = selection.query_result
    selected = selection.selected_sources
    direct_selection = None
    comparison = None
    selection_method = "catalog"
    if repository.repository_kind not in {"ept", "copc"} and request.direct_header_fallback:
        direct_selection = DirectLidarFolderSelector().select(repository.normalized_path, request.polygon, repository_crs_override=request.repository_crs_override or repository.source_crs, recursive=request.recursive)
        comparison = compare_selection_methods(direct_selection, selected, catalog_seconds=0 if query is None else query.query_seconds)
        if (not selected and direct_selection.selected_sources and request.selection_mode in {"automatic", "direct_header_scan"}) or request.selection_mode == "direct_header_scan":
            selected = direct_selection.selected_sources
            selection_method = "direct_header_scan"
            warnings.append("Catalog selection found no files. Direct Header Scan selected real source files; repair or rebuild the catalog when convenient.")
            selection = _selection_from_direct(repository, request, query_geometry, direct_selection, service)
    inventory = LidarInventory(repository.normalized_path, selected, cache_path=Path(catalog_path))
    warnings.extend(message.to_text() for message in selection.warnings)
    blockers.extend(message.to_text() for message in selection.blockers)
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
    warnings.extend(plan.warnings)
    if repository.repository_kind not in {"ept", "copc"}:
        blockers.extend(selected_path_invariant(selected, ordinary=True))
    if not selected and not any("No LiDAR coverage" in item or "Catalog" in item or "spatial bounds" in item for item in blockers):
        blockers.append("No LiDAR coverage was found for this area.")
    point_count = selection.workload_estimate.point_estimate if selection.workload_estimate is not None else (None if query is None else query.estimated_point_count)
    source_bytes = 0 if query is None else query.estimated_bytes
    if repository.repository_kind not in {"ept", "copc"}:
        if selection_method == "direct_header_scan":
            warnings.extend(direct_selection.warnings if direct_selection is not None else ())
        if len(selected) >= DEFAULT_POLYGON_SOURCE_WARNING:
            warnings.append("Large polygon batch: many intersecting sources selected.")
        if point_count is not None and point_count >= DEFAULT_POLYGON_POINT_WARNING:
            warnings.append("Large polygon batch: estimated point count is high; run sequentially unless carefully tested.")
    if query is not None and query.metadata_error_count:
        warnings.append(f"{query.metadata_error_count:,} catalog source(s) have metadata errors; polygon selection may be incomplete until they are retried.")
    if source_bytes >= DEFAULT_POLYGON_SIZE_WARNING_BYTES:
        warnings.append("Large polygon batch: source file size is high; ensure disk and memory headroom.")
    options = request.shared_execution_options or BatchExecutionOptions.from_batch_settings(request.settings)
    concurrency = requested_effective_concurrency(options, source_types={source.source_type for source in selected}, product_count=len(request.products))
    polygon_context = service.last_polygon_context or _fallback_polygon_context(request.polygon, query_geometry)
    execution_plan = build_polygon_execution_plan(
        repository=repository,
        polygon_context=polygon_context,
        source_selection=selection,
        products=tuple(product.value for product in request.products),
        shared_batch_options=options,
        polygon_batch_options=request.polygon_options,
        requested_concurrency=int(concurrency["requested_concurrent_jobs"]),
        effective_concurrency=int(concurrency["effective_concurrent_jobs"]),
        output_folder=request.output_folder,
        backend_ready=backend_ready,
        backend_message=backend_message,
    )
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
        catalog_skipped_count=selection.catalog_skipped_count,
        backend_ready=backend_ready,
        backend_message=backend_message,
        spatial_alignment_status=_spatial_alignment_status(selection),
        repository=repository,
        source_selection=selection,
        execution_plan=execution_plan,
        structured_warnings=selection.warnings,
        structured_blockers=selection.blockers,
        plan_signature=execution_plan.plan_signature,
        selection_method=selection_method,
        direct_selection=direct_selection,
        selection_comparison=comparison,
    )


def _report_from_direct_selection(request, repository, service, query_geometry, batch_folder, manifest_path, direct, backend_ready, backend_message, catalog_path):
    inventory = LidarInventory(repository.normalized_path, direct.selected_sources, cache_path=Path(catalog_path))
    warnings = list(direct.warnings)
    blockers = list(direct.blockers)
    if not backend_ready:
        blockers.append("Managed processing backend cannot import PyForestScan. Repair or rebuild the backend from Environment.")
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
    selection = _selection_from_direct(repository, request, query_geometry, direct, service)
    options = request.shared_execution_options or BatchExecutionOptions.from_batch_settings(request.settings)
    polygon_context = service.last_polygon_context or _fallback_polygon_context(request.polygon, query_geometry)
    concurrency = requested_effective_concurrency(options, source_types={source.source_type for source in direct.selected_sources}, product_count=len(request.products))
    execution_plan = build_polygon_execution_plan(
        repository=repository,
        polygon_context=polygon_context,
        source_selection=selection,
        products=tuple(product.value for product in request.products),
        shared_batch_options=options,
        polygon_batch_options=request.polygon_options,
        requested_concurrency=int(concurrency["requested_concurrent_jobs"]),
        effective_concurrency=int(concurrency["effective_concurrent_jobs"]),
        output_folder=request.output_folder,
        backend_ready=backend_ready,
        backend_message=backend_message,
    )
    return PolygonBatchPreflightReport(
        request=request,
        inventory=inventory,
        plan=plan,
        ready=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        selected_sources=direct.selected_sources,
        skipped_sources=(),
        estimated_point_count=_estimated_points_for_sources(direct.selected_sources),
        estimated_source_bytes=sum(source.size_bytes for source in direct.selected_sources),
        batch_folder=batch_folder,
        manifest_path=manifest_path,
        catalog_path=Path(catalog_path),
        query_geometry=query_geometry,
        query_result=None,
        catalog_skipped_count=0,
        backend_ready=backend_ready,
        backend_message=backend_message,
        spatial_alignment_status="Ready" if direct.ready else "Needs review",
        repository=repository,
        source_selection=selection,
        execution_plan=execution_plan,
        structured_warnings=selection.warnings,
        structured_blockers=selection.blockers,
        plan_signature=execution_plan.plan_signature,
        selection_method="direct_header_scan",
        direct_selection=direct,
        selection_comparison=None,
    )


def _selection_from_direct(repository, request, query_geometry, direct, service):
    from .polygon_source_selection import PolygonSourceSelectionResult, PreflightMessage, SpatialEnvelope

    transformed = SpatialEnvelope.from_bounds(query_geometry.envelope, query_geometry.catalog_crs)
    setattr(service, "_last_polygon_context", _fallback_polygon_context(request.polygon, query_geometry))
    warnings = tuple(PreflightMessage("DIRECT_HEADER_SCAN", "warning", "Direct Header Scan", item) for item in direct.warnings)
    blockers = tuple(PreflightMessage("DIRECT_SELECTION_BLOCKED", "blocker", "Selection blocked", item) for item in direct.blockers)
    return PolygonSourceSelectionResult(
        repository_kind=repository.repository_kind,
        logical_candidates=direct.selected_sources,
        selected_sources=direct.selected_sources,
        rejected_sources=(),
        transformed_polygon=query_geometry.exact_polygon_wkt,
        transformed_envelope=transformed,
        source_extent=None,
        overlap_result="yes" if direct.selected_sources else "no",
        exact_intersection_result="direct_header_scan",
        warnings=warnings,
        blockers=blockers,
        timings={"direct_header_scan": direct.elapsed_seconds},
        query_result=None,
        catalog_skipped_count=len(direct.rejected_sources),
        workload_estimate=None,
    )


def _estimated_points_for_sources(sources):
    counts = [source.point_count for source in sources]
    if not counts or any(count is None for count in counts):
        return None
    return int(sum(count for count in counts if count is not None))


def polygon_preflight_text(report: PolygonBatchPreflightReport) -> str:
    """Format a concise Batch-page polygon preflight report."""
    query = report.query_result
    repository_kind = getattr(getattr(report, "repository", None), "repository_kind", "")
    repository_type = "EPT dataset" if repository_kind == "ept" or (_is_logical_spatial_report(report) and report.selected_sources[0].source_type == "ept") else "LiDAR repository"
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
        f"Selection method: {report.selection_method}",
        f"Plan status: Current",
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
        if repository_kind == "ept":
            lines.append("- Selection method: native EPT extent overlap")
        else:
            lines.append(f"- Catalog integrity: {getattr(query, 'catalog_integrity_status', 'Unknown')}")
            lines.append(f"- Usable spatial sources: {getattr(query, 'catalog_usable_source_count', 0)}")
            lines.append(f"- Skipped catalog sources: {report.catalog_skipped_count}")
            skip_counts = getattr(query, 'skip_reason_counts', None) or {}
            for code, count in sorted(skip_counts.items()):
                lines.append(f"  - {count:,} {code}")
        lines.append(f"- Metadata errors: {query.metadata_error_count}")
    if report.source_selection is not None:
        lines.append(f"- Polygon original CRS: {report.request.polygon.source_crs}")
        lines.append(f"- Repository CRS: {getattr(report.repository, 'source_crs', None) or report.query_geometry.catalog_crs}")
        lines.append(f"- Comparison CRS: {report.source_selection.transformed_envelope.crs}")
        lines.append(f"- Transformed polygon bounds: {report.source_selection.transformed_envelope.xmin:g}, {report.source_selection.transformed_envelope.ymin:g}, {report.source_selection.transformed_envelope.xmax:g}, {report.source_selection.transformed_envelope.ymax:g}")
        if report.source_selection.source_extent is not None:
            extent = report.source_selection.source_extent
            lines.append(f"- Repository extent: {extent.xmin:g}, {extent.ymin:g}, {extent.xmax:g}, {extent.ymax:g}")
        lines.append(f"- Overlap: {'Yes' if report.source_selection.overlap_result == 'yes' else 'No'}")
        if report.source_selection.rejected_sources:
            lines.append("- Rejected sources:")
            for rejected in report.source_selection.rejected_sources[:5]:
                lines.append(f"  - {rejected.path} ({rejected.rejection_code}): {rejected.user_reason}")
    if report.plan_signature:
        lines.append(f"- Plan signature: {report.plan_signature[:16]}")
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
    if not _is_logical_spatial_report(report):
        path_blockers = selected_path_invariant(report.selected_sources, ordinary=True)
        if path_blockers:
            raise ValueError("; ".join(path_blockers))
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
    result = _apply_mask_failures(result, mask_results, report)
    result = _register_polygon_outputs(result, report, mask_results)
    write_polygon_batch_manifest(report, clip_records, batch_folder=batch_folder, mask_records=[_mask_record(item) for item in mask_results])
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
        "shared_execution_options": _shared_options(report).to_dict(),
        "polygon_options": report.request.polygon_options.to_dict(),
        "option_applicability": [item.to_dict() for item in _option_applicability(report)],
        "concurrency": requested_effective_concurrency(_shared_options(report), source_types=_source_types(report), product_count=len(report.request.products)),
        "execution_plan": None if report.execution_plan is None else report.execution_plan.to_dict(),
        "source_aware_chm_plan": _source_aware_chm_plan_dict(report),
        "plan_signature": report.plan_signature,
        "repository_identity": None if report.repository is None else report.repository.to_dict(),
        "source_selection": None if report.source_selection is None else report.source_selection.to_dict(),
        "selection_method": report.selection_method,
        "selected_source_paths": [str(source.path) for source in report.selected_sources],
        "selected_path_invariant": {"ordinary": not _is_logical_spatial_report(report), "readable_path_count": sum(1 for source in report.selected_sources if Path(source.path).is_file()), "selected_source_count": len(report.selected_sources)},
        "direct_selection": None if report.direct_selection is None else {
            "discovered_file_count": report.direct_selection.discovered_file_count,
            "metadata_read_count": report.direct_selection.metadata_read_count,
            "usable_source_count": report.direct_selection.usable_source_count,
            "intersecting_source_paths": [str(path) for path in report.direct_selection.intersecting_source_paths],
            "blockers": list(report.direct_selection.blockers),
            "warnings": list(report.direct_selection.warnings),
        },
        "query": {
            "envelope": report.query_geometry.envelope.__dict__,
            "ept_bounds": EptBounds.from_value(report.query_geometry.ept_bounds, crs=report.query_geometry.catalog_crs).to_json(),
            "pdal_bounds_expression": EptBounds.from_value(report.query_geometry.ept_bounds, crs=report.query_geometry.catalog_crs).to_pdal_range_string(),
            "bounds_query_crs": report.query_geometry.catalog_crs,
            "ept_query_crs": report.query_geometry.catalog_crs,
            "spatial_alignment": report.spatial_alignment_status,
            "spatial_alignment_details": None if report.source_selection is None or report.source_selection.spatial_alignment is None else report.source_selection.spatial_alignment.to_dict(),
            "crs_resolution_source": "" if report.repository is None else getattr(report.repository, "crs_resolution_source", ""),
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
            "polygon_transformed_crs": report.query_geometry.catalog_crs,
            "repository_crs": "" if report.repository is None else getattr(report.repository, "source_crs", None),
            "ept_query_crs": report.query_geometry.catalog_crs,
            "ept_source_crs": report.query_geometry.catalog_crs,
            "bounds_query_crs": report.query_geometry.catalog_crs,
            "clipping_polygon_crs": report.query_geometry.catalog_crs,
            "clipping_geometry_crs": report.query_geometry.catalog_crs,
            "processing_crs": report.query_geometry.catalog_crs,
            "output_crs": report.query_geometry.catalog_crs if _is_logical_spatial_report(report) else report.request.polygon.processing_crs,
            "transformation_required": bool(report.source_selection and report.source_selection.spatial_alignment and report.source_selection.spatial_alignment.transformation_required),
            "transformation_validation_result": report.spatial_alignment_status,
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



def build_source_aware_chm_plan(report: PolygonBatchPreflightReport):
    """Build the bounded CHM plan used by prerun, manifests, and the future executor."""
    if ProductType.CHM not in report.request.products or not report.selected_sources:
        return None
    bounds = report.query_geometry.envelope
    envelope = SpatialExtent(bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax)
    native = []
    for source in report.selected_sources:
        source_bounds = envelope if source.bounds is None or getattr(report.repository, "repository_kind", "") == "ept" else SpatialExtent(source.bounds.xmin, source.bounds.ymin, source.bounds.xmax, source.bounds.ymax)
        native.append(NativeSource(Path(source.path), source_bounds, source.size_bytes, source.point_count, source.source_type))
    return SourceAwareWorkPlanner().plan(
        repository_kind=getattr(report.repository, "repository_kind", "folder"),
        sources=tuple(native),
        polygon_envelope=envelope,
        processing_crs=report.query_geometry.catalog_crs or report.request.polygon.processing_crs,
        product="chm",
        resolution=report.request.settings.grid_resolution,
        available_memory_bytes=8 * 1024**3,
        cpu_count=max(1, _shared_options(report).worker_count),
        profile="recommended",
    )

def _source_aware_chm_plan_dict(report: PolygonBatchPreflightReport):
    plan = build_source_aware_chm_plan(report)
    return None if plan is None else plan.to_dict()

def selected_source_paths(report: PolygonBatchPreflightReport) -> tuple[Path, ...]:
    """Return intersecting source paths for tests and UI summaries."""
    return tuple(source.path for source in report.selected_sources)


def _spatial_alignment_status(selection: PolygonSourceSelectionResult) -> str:
    alignment = selection.spatial_alignment
    if alignment is None:
        return "Ready" if not selection.blockers else "Needs review"
    if alignment.ready:
        return "Ready"
    if alignment.status == "crs_malformed":
        return "EPT CRS incomplete"
    if alignment.status == "transformation_unavailable":
        return "CRS transform unavailable"
    return "Needs review"


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



def _fallback_polygon_context(polygon, query_geometry):
    from .polygon_source_selection import PolygonSpatialContext, SpatialEnvelope, polygon_normalization_report

    envelope = SpatialEnvelope.from_bounds(query_geometry.envelope, query_geometry.catalog_crs)
    return PolygonSpatialContext(
        original_geometry=polygon.geometry_wkt,
        original_crs=polygon.source_crs,
        normalized_geometry=polygon.geometry_wkt,
        processing_geometry=polygon.geometry_wkt,
        processing_crs=polygon.processing_crs,
        source_geometry=query_geometry.exact_polygon_wkt,
        source_crs=query_geometry.catalog_crs,
        source_envelope=envelope,
        normalization_report=polygon_normalization_report(polygon),
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
    repository_kind = getattr(getattr(report, "repository", None), "repository_kind", "")
    return bool(report.selected_sources) and len(report.selected_sources) == 1 and repository_kind == "ept" and report.selected_sources[0].source_type == "ept"


def _execute_logical_spatial_batch(report: PolygonBatchPreflightReport, adapter: PyForestScanAdapter, batch_folder: Path, *, item_callback=None) -> BatchResult:
    started_at = datetime.now(timezone.utc).isoformat()
    source = report.selected_sources[0]
    job_folder = batch_folder / "polygon_jobs" / unique_polygon_job_id(source.source_type)
    context = batch_run_context(Path(source.path), job_folder, reuse_existing=True).ensure_directories()
    for child in ("inputs", "staging", "outputs", "logs", "diagnostics"):
        (job_folder / child).mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    stages = _polygon_progress_stages(report.request.products)
    scalable_plan = build_source_aware_chm_plan(report)
    if report.request.products == (ProductType.CHM,) and scalable_plan is not None and len(scalable_plan.work_units) > 1:
        return _execute_source_aware_chm(report, adapter, batch_folder, context, source, scalable_plan, item_callback=item_callback)
    try:
        _emit_polygon_stage(item_callback, source, context, "Preparing Inputs", "Preparing durable polygon job workspace.")
        write_polygon_batch_manifest(report, [{"source": str(source.path), "clipped": "native", "points": str(source.point_count or "unknown"), "bounds_used": str(report.query_geometry.ept_bounds), "job_folder": str(job_folder)}], batch_folder=batch_folder)
        for product in report.request.products:
            _emit_polygon_stage(item_callback, source, context, "Generating Product", f"Generating {product.value}.")
            result_path = _logical_product_output_path(context.outputs_dir, product)
            request = _logical_product_request(product, source.path, result_path, report)
            result = _run_logical_product(adapter, product, request)
            outputs.append(Path(getattr(result, "output_path")))
        mask_results = _mask_paths(outputs, report)
        status = "completed"
        message = "Logical EPT/COPC source processed through PBM backend and exact polygon finalization."
        failures = [item for item in mask_results if item.status == "failed"]
        if failures and report.request.polygon_options.mask_failure_policy == "fail_product":
            status = "failed"
            message = "; ".join(item.message for item in failures)
        item = BatchItemResult(Path(source.path), context, status, message, tuple(outputs), _requested_extent_summary(report))
    except Exception as exc:  # noqa: BLE001
        mask_results = ()
        item = BatchItemResult(Path(source.path), context, "failed", _friendly_polygon_execution_error(str(exc)), tuple(outputs), _requested_extent_summary(report))
    finished_at = datetime.now(timezone.utc).isoformat()
    result = BatchResult(
        "polygon-logical",
        report.request.title,
        started_at,
        finished_at,
        batch_folder,
        (item,),
        batch_folder / "batch_summary.json",
        batch_folder / "batch_summary.csv",
        batch_folder / "batch_summary.html",
        load_outputs_after_completion=_shared_options(report).load_outputs_after_completion,
    )
    result = _register_polygon_outputs(result, report, mask_results)
    write_polygon_batch_manifest(report, [{"source": str(source.path), "clipped": "native", "points": str(source.point_count or "unknown"), "bounds_used": str(report.query_geometry.ept_bounds), "job_folder": str(context.run_folder)}], batch_folder=batch_folder, mask_records=[_mask_record(item) for item in mask_results])
    if item_callback is not None:
        item_callback(item)
    return write_batch_summaries(result)



def _execute_source_aware_chm(report, adapter, batch_folder, context, source, plan, *, item_callback=None):
    """Execute bounded CHM work units, checkpoint cores, mosaic, and mask final output."""
    started_at = datetime.now(timezone.utc).isoformat()
    signature = report.plan_signature or getattr(report.execution_plan, "plan_signature", "") or "source-aware-chm"
    checkpoint = CheckpointStore(context.run_folder / "work_units", signature)

    def execute_unit(unit, attempt):
        unit_folder = context.run_folder / "work_units" / unit.work_unit_id
        buffered_path = unit_folder / "outputs" / "chm_buffered.tif"
        core_path = unit_folder / "outputs" / "chm_core.tif"
        buffered_path.parent.mkdir(parents=True, exist_ok=True)
        request = _logical_product_request(ProductType.CHM, source.path, buffered_path, report)
        read = unit.read_extent
        request = replace(request, bounds=EptBounds.from_value(((read.xmin, read.xmax), (read.ymin, read.ymax)), crs=report.query_geometry.catalog_crs).to_json())
        request = replace(request, work_unit_id=unit.work_unit_id, attempt_id=f"attempt-{attempt}", completed_count=max(0, unit.execution_order-1), total_count=len(plan.work_units), inspect_hag_suitability=True)
        result = _run_logical_product(adapter, ProductType.CHM, request)
        _extract_core_raster(Path(result.output_path), core_path, unit.core_extent)
        return WorkUnitResult(unit.work_unit_id, "Complete", core_path, attempt_count=attempt, metrics={"core_extent": unit.core_extent.__dict__, "read_extent": unit.read_extent.__dict__, "hag_method": "automatic_per_work_unit"})

    def progress(event):
        if item_callback is None:
            return
        message = event.message
        if event.stop_reason:message += f" {event.stop_reason}"
        _emit_polygon_stage(item_callback, source, context, event.stage, message)

    scheduler = PolygonProductWorkScheduler(plan.work_units, execute_unit, checkpoint, concurrency=plan.concurrency_limit, retry_count=2, transient=_transient_work_unit_error, progress_callback=progress)
    results = scheduler.run()
    failed = tuple(item for item in results if item.status == "Failed")
    pending = tuple(item for item in results if item.status == "Pending")
    final_unmasked = context.run_folder / "mosaics" / "chm.tif"
    outputs = []
    mask_results = ()
    if failed or pending:
        status = "failed"
        first = failed[0] if failed else pending[0]
        message = scheduler.stop_reason or f"{len(failed)} CHM work units failed and {len(pending)} remain pending. First affected unit {first.work_unit_id}: {first.message}"
    else:
        _mosaic_core_rasters(tuple(item.output_path for item in results if item.output_path), final_unmasked, plan)
        final_path = context.outputs_dir / "chm.tif"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_unmasked.replace(final_path)
        outputs = [final_path]
        mask_results = _mask_paths(outputs, report)
        failures = [item for item in mask_results if item.status == "failed"]
        status = "failed" if failures else "completed"
        message = "; ".join(item.message for item in failures) if failures else f"Source-aware CHM completed from {len(results)} verified work units."
    item = BatchItemResult(Path(source.path), context, status, message, tuple(outputs), _requested_extent_summary(report))
    result = BatchResult("polygon-source-aware-chm", report.request.title, started_at, datetime.now(timezone.utc).isoformat(), batch_folder, (item,), batch_folder / "batch_summary.json", batch_folder / "batch_summary.csv", batch_folder / "batch_summary.html", load_outputs_after_completion=_shared_options(report).load_outputs_after_completion)
    result = _register_polygon_outputs(result, report, mask_results)
    write_polygon_batch_manifest(report, [{"source": str(source.path), "strategy": "bounded_work_units", "work_units": str(len(plan.work_units)), "job_folder": str(context.run_folder)}], batch_folder=batch_folder, mask_records=[_mask_record(x) for x in mask_results])
    if item_callback is not None: item_callback(item)
    return write_batch_summaries(result)

def _extract_core_raster(source_path: Path, output_path: Path, extent: SpatialExtent) -> None:
    try:
        from osgeo import gdal
    except ImportError as exc:
        raise RuntimeError("GDAL is required to extract aligned CHM core tiles.") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".partial.tif")
    dataset = gdal.Translate(str(temporary), str(source_path), projWin=(extent.xmin, extent.ymax, extent.xmax, extent.ymin), creationOptions=("TILED=YES", "COMPRESS=DEFLATE"))
    if dataset is None: raise RuntimeError(f"Raster core extraction failed: {source_path}")
    dataset = None
    temporary.replace(output_path)

def _mosaic_core_rasters(paths, output_path: Path, plan) -> None:
    if len(paths) != len(plan.work_units) or any(path is None or not Path(path).is_file() for path in paths):
        raise RuntimeError("CHM mosaic requires every verified core work-unit raster.")
    try:
        from osgeo import gdal
    except ImportError as exc:
        raise RuntimeError("GDAL is required to create the aligned CHM mosaic.") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vrt = output_path.with_suffix(".vrt"); temporary = output_path.with_suffix(".partial.tif")
    built = gdal.BuildVRT(str(vrt), [str(path) for path in paths], resolution="user", xRes=plan.grid.resolution, yRes=plan.grid.resolution, outputBounds=(plan.grid.total_extent.xmin, plan.grid.total_extent.ymin, plan.grid.total_extent.xmax, plan.grid.total_extent.ymax), srcNodata=plan.grid.nodata, VRTNodata=plan.grid.nodata)
    if built is None: raise RuntimeError("CHM VRT mosaic construction failed.")
    built = None
    translated = gdal.Translate(str(temporary), str(vrt), creationOptions=("TILED=YES", "COMPRESS=DEFLATE"))
    if translated is None: raise RuntimeError("CHM transactional mosaic write failed.")
    translated = None; vrt.unlink(missing_ok=True); temporary.replace(output_path)

def _transient_work_unit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "all points collinear" in text or "invalid" in text or "crs" in text: return False
    return any(token in text for token in ("network", "connection", "temporarily", "timeout", "reset by peer"))

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
    if "all points collinear" in message.lower():
        return "Ground normalization could not construct a surface for part of the selected area. Technical cause: All points collinear. View scientific details before retrying with an approved alternative."
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
    return _mask_paths(paths, report)


def _mask_paths(paths: list[Path], report: PolygonBatchPreflightReport) -> tuple[RasterMaskResult, ...]:
    if not report.request.polygon_options.exact_raster_mask:
        return ()
    options = RasterMaskOptions(
        engine=report.request.polygon_options.mask_engine,
        all_touched=report.request.polygon_options.all_touched,
        crop_to_polygon_extent=report.request.polygon_options.crop_to_polygon_extent,
        nodata=report.request.polygon_options.mask_nodata if report.request.polygon_options.mask_nodata is not None else -9999.0,
        retain_unmasked_intermediate=report.request.polygon_options.retain_unmasked_intermediate,
    )
    return apply_polygon_mask_to_outputs(
        paths,
        report.query_geometry.exact_polygon_wkt,
        polygon_crs=report.request.polygon.source_crs,
        processing_crs=report.request.polygon.processing_crs,
        options=options,
    )


def _apply_mask_failures(result: BatchResult, mask_results: tuple[RasterMaskResult, ...], report: PolygonBatchPreflightReport) -> BatchResult:
    if report.request.polygon_options.mask_failure_policy != "fail_product":
        return result
    failed = {Path(item.path) for item in mask_results if item.status == "failed"}
    if not failed:
        return result
    next_items = []
    for item in result.items:
        if any(Path(output) in failed for output in item.outputs):
            next_items.append(replace(item, status="failed", message="Exact polygon mask failed; unmasked raster is not presented as final output."))
        else:
            next_items.append(item)
    return replace(result, items=tuple(next_items))


def _register_polygon_outputs(result: BatchResult, report: PolygonBatchPreflightReport, mask_results: tuple[RasterMaskResult, ...]) -> BatchResult:
    successful_masks = {Path(item.path) for item in mask_results if item.status == "masked"}
    outputs = []
    group_name = f"PyForestScan/{report.request.polygon.source_description or 'Polygon Area'}"
    for item in result.items:
        if item.status != "completed":
            continue
        for output in item.outputs:
            path = Path(output)
            if not path.exists():
                continue
            outputs.append(
                generated_output_for_path(
                    path,
                    job_id=result.batch_id,
                    product_key=_product_key_from_output(path),
                    source_mode="polygon_area_processing",
                    masked=path in successful_masks or not is_maskable_raster(path),
                    mask_geometry_id=report.request.polygon.source_description,
                    group_name=group_name,
                )
            )
    if not outputs:
        return result
    registry_path = write_output_registry(outputs, result.batch_folder)
    return replace(result, output_registry_path=registry_path)


def _product_key_from_output(path: Path) -> str:
    stem = path.stem.lower()
    if "canopy_cover" in stem:
        return "canopy_cover"
    if "point_density" in stem:
        return "point_density"
    if "voxel" in stem:
        return "voxel_stat"
    for key in ("chm", "dtm", "pad", "pai", "fhd", "rumple"):
        if stem == key or key in stem:
            return key
    return "output"


def _mask_record(item: RasterMaskResult) -> dict[str, object]:
    return {
        "path": str(item.path),
        "status": item.status,
        "message": item.message,
        "engine": item.engine,
        "output_path": str(item.output_path) if item.output_path else "",
        "intermediate_path": str(item.intermediate_path) if item.intermediate_path else "",
        "masked": item.masked,
        "nodata": item.nodata,
        "band_count": item.band_count,
    }


def _shared_options(report: PolygonBatchPreflightReport) -> BatchExecutionOptions:
    return report.request.shared_execution_options or BatchExecutionOptions.from_batch_settings(report.request.settings)


def _source_types(report: PolygonBatchPreflightReport) -> set[str]:
    return {str(source.source_type).lower() for source in report.selected_sources}


def _option_applicability(report: PolygonBatchPreflightReport):
    return polygon_option_applicability(_shared_options(report), source_types=_source_types(report), product_count=len(report.request.products))


def _planned_polygon_batch_folder(output_folder: Path) -> Path:
    return Path(output_folder) / "pyforestscan_polygon_batch_planned"


def _safe_stem(path: Path) -> str:
    stem = path.parent.name if path.name.lower() == "ept.json" else path.stem
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "source"
