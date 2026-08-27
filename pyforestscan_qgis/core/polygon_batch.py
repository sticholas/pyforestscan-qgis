"""Polygon area batch preflight and execution helpers."""

from __future__ import annotations

import json
import hashlib
import os
import pickle
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
from .effective_source_spatial_profile import shared_repository_crs
from .processing_spatial_context import EffectiveSpatialMode, SourceLocalFallbackPolicy, default_source_local_policy_store
from .spatial_reference_resolver import default_spatial_assignment_store
from .lidar_catalog import catalog_summary
from .lidar_catalog_models import CatalogThresholds, LidarCatalogQueryResult, PolygonQueryGeometry, default_lidar_catalog_path
from .spatial_selection import Bounds2D
from .lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from .polygon_source_selection import PolygonExecutionPlan, PolygonSourceSelectionResult, PolygonSourceSelectionService, build_polygon_execution_plan
from .lidar_inventory import LidarInventory, LidarSourceRecord
from .lidar_source_metadata import LidarSourceMetadata
from .polygon_processing import PolygonProcessingPlan, build_polygon_processing_plan
from .polygon_source import NormalizedPolygonSelection
from .polygon_transport import polygon_execution_input_from_selection, unique_polygon_job_id
from .raster_mask import RasterMaskOptions, RasterMaskResult, apply_polygon_mask_to_outputs, is_maskable_raster
from .output_registry import generated_output_for_path, write_output_registry
from .polygon_lidar_processing import selected_path_invariant
from .source_aware_processing import AlignedRasterGrid, NativeSource, SourceAwareWorkPlanner, SpatialExtent
from .rumple_adaptive import derive_rumple_grid, rumple_core_extent
from .rumple_raster_io import create_rumple_raster_from_chm, raster_totals, write_rumple_summary
from .durable_errors import DurableErrorRecord, write_recent_error
from .work_unit_scheduler import CheckpointStore, PolygonProductWorkScheduler, WorkUnitResult
from .hag_strategy import hag_method_signature
from .types import CanopyCoverRequest, ChmRequest, DtmRequest, FhdRequest, HagNormalizationRequest, PadRequest, PaiRequest, PointDensityRequest, ProductType, RumpleRequest, VoxelStatRequest
from .backend.processing_engine import ProcessingRuntimeToken
from .source_alternatives import SourceRelationship, canonicalize_source_alternatives

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
    spatial_policy: SourceLocalFallbackPolicy | None = None
    runtime_token: ProcessingRuntimeToken | None = None


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
    source_alternative_detections: tuple[object, ...] = ()

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def run_polygon_batch_preflight(request: PolygonBatchRequest, *, backend_probe: Callable[[], tuple[bool, str]] | None = None) -> PolygonBatchPreflightReport:
    """Resolve repository identity, select sources, and build one execution plan."""
    active_spatial_policy = request.spatial_policy or default_source_local_policy_store().read()
    if request.spatial_policy is None:
        request = replace(request, spatial_policy=active_spatial_policy)
    assigned_crs, _assignment_source = shared_repository_crs(request.lidar_folder)
    effective_repository_crs = assigned_crs or request.repository_crs_override
    if effective_repository_crs != request.repository_crs_override:
        request = replace(request, repository_crs_override=effective_repository_crs)
    service = PolygonSourceSelectionService()
    repository = service.resolve_repository(request.lidar_folder, request.catalog_path)
    if effective_repository_crs and repository.repository_kind != "ept":
        repository = replace(repository, source_crs=effective_repository_crs, resolution_method="shared_spatial_assignment")
    catalog_path = repository.catalog_path or request.catalog_path or default_lidar_catalog_path(repository.normalized_path)
    query_geometry = derive_polygon_query_geometry(request.polygon, catalog_crs=repository.source_crs or request.catalog_crs)
    batch_folder = request.batch_folder or _planned_polygon_batch_folder(request.output_folder)
    manifest_path = batch_folder / POLYGON_MANIFEST_NAME
    empty_inventory = LidarInventory(repository.normalized_path, ())
    blockers: list[str] = []
    warnings: list[str] = list(query_geometry.warnings)
    backend_ready, backend_message, runtime_token = _probe_pbm_backend(backend_probe, tuple(product.value for product in request.products))
    if runtime_token is not None:
        request = replace(request, runtime_token=runtime_token)
    if not backend_ready:
        blockers.append("Managed processing backend cannot import PyForestScan. Repair or rebuild the backend from Environment.")
    if not request.products:
        blockers.append("Select at least one product.")
    if not Path(repository.normalized_path).is_dir():
        blockers.append(f"LiDAR repository does not exist: {repository.normalized_path}")
    if repository.repository_kind != "ept" and (request.selection_mode == "direct_header_scan" or (request.direct_header_fallback and not Path(catalog_path).exists())):
        direct = DirectLidarFolderSelector(spatial_policy=active_spatial_policy).select(repository.normalized_path, request.polygon, repository_crs_override=request.repository_crs_override or repository.source_crs, recursive=request.recursive)
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
    selection = service.select_sources(repository, request.polygon, catalog_crs=repository.source_crs or request.catalog_crs, thresholds=request.thresholds, spatial_policy=active_spatial_policy)
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
        direct_selection = DirectLidarFolderSelector(spatial_policy=active_spatial_policy).select(repository.normalized_path, request.polygon, repository_crs_override=request.repository_crs_override or repository.source_crs, recursive=request.recursive)
        comparison = compare_selection_methods(direct_selection, selected, catalog_seconds=0 if query is None else query.query_seconds)
        catalog_status = "" if query is None else str(getattr(query, "catalog_integrity_status", ""))
        catalog_broken = bool(query is not None and catalog_status not in {"Healthy", "Healthy with validated repository CRS override", "Healthy with effective repository assignment"})
        trusted_repository_interpretation = bool(request.repository_crs_override or getattr(repository, "source_crs", None))
        if (not selected and direct_selection.selected_sources and (not catalog_broken or trusted_repository_interpretation) and request.selection_mode in {"automatic", "direct_header_scan"}) or request.selection_mode == "direct_header_scan":
            selected = direct_selection.selected_sources
            selection_method = "direct_header_scan"
            warnings.append("Catalog selection found no files. Direct Header Scan selected real source files; repair or rebuild the catalog when convenient.")
            selection = _selection_from_direct(repository, request, query_geometry, direct_selection, service)
    selected, alternative_detections = canonicalize_source_alternatives(tuple(selected))
    if any(getattr(context, "mode", None) is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE for context in getattr(selection, "spatial_contexts", ())):
        warnings = [item for item in warnings if "cannot yet be compared" not in str(item).lower()]
    alternatives = tuple(item for item in alternative_detections if item.relationship in {SourceRelationship.POTENTIAL_ALTERNATIVE_REPRESENTATION, SourceRelationship.DUPLICATE})
    ambiguous_alternatives = tuple(item for item in alternative_detections if item.relationship is SourceRelationship.UNKNOWN)
    if alternatives:
        warnings.append("Two LiDAR files appear to represent the same area. The recommended prepared source was selected; use Advanced source selection to override.")
        selection = replace(selection, selected_sources=selected)
        if selection.workload_estimate is not None:
            count = _estimated_points_for_sources(selected)
            selection = replace(selection, workload_estimate=replace(selection.workload_estimate, point_estimate=count, lower_bound=count, upper_bound=count, method="Canonical source-point sum after alternative-representation detection", assumptions=("Duplicate-like source representations are counted once.",)))
    if ambiguous_alternatives:
        blockers.append("Two LiDAR files have overlapping source identity but no safe canonical representation could be selected. Choose one source explicitly in Advanced source selection.")
    inventory = LidarInventory(repository.normalized_path, selected, cache_path=Path(catalog_path))
    warnings.extend(message.to_text() for message in selection.warnings)
    if any(getattr(context, "mode", None) is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE for context in getattr(selection, "spatial_contexts", ())):
        warnings = [item for item in warnings if "cannot yet be compared" not in str(item).lower()]
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
    point_count = _estimated_points_for_sources(selected) if alternatives else (selection.workload_estimate.point_estimate if selection.workload_estimate is not None else (None if query is None else query.estimated_point_count))
    source_bytes = sum(source.size_bytes for source in selected) if alternatives else (0 if query is None else query.estimated_bytes)
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
        source_alternative_detections=alternative_detections,
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
        spatial_alignment_status=_direct_spatial_alignment_status(direct),
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
    raw_overlap_values = [item.raw_overlap for item in direct.rejected_sources if item.raw_overlap is not None]
    overlap_result = "yes" if direct.selected_sources or any(raw_overlap_values) else ("no" if raw_overlap_values else "not_evaluated")
    return PolygonSourceSelectionResult(
        repository_kind=repository.repository_kind,
        logical_candidates=direct.selected_sources,
        selected_sources=direct.selected_sources,
        rejected_sources=(),
        transformed_polygon=query_geometry.exact_polygon_wkt,
        transformed_envelope=transformed,
        source_extent=None,
        overlap_result=overlap_result,
        exact_intersection_result="direct_header_scan",
        warnings=warnings,
        blockers=blockers,
        timings={"direct_header_scan": direct.elapsed_seconds},
        query_result=None,
        catalog_skipped_count=len(direct.rejected_sources),
        workload_estimate=None,
        spatial_contexts=direct.spatial_contexts,
    )


def _direct_spatial_alignment_status(direct: PolygonLidarSelectionResult) -> str:
    if any(context.mode is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE for context in direct.spatial_contexts):
        return "Assumed"
    return "Verified" if direct.ready else "Blocked"


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
    work_plan = build_source_aware_chm_plan(report)
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
        *( [] if work_plan is None else [f"Processing grid: {work_plan.candidate_count} candidate areas",f"Inside polygon: {work_plan.required_count} required areas",f"Outside polygon: {work_plan.skipped_count} skipped areas"] ),
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
        overlap = report.source_selection.overlap_result
        lines.append(f"- Raw coordinate overlap: {'Yes' if overlap == 'yes' else ('No' if overlap == 'no' else 'Not evaluated')}")
        lines.append(f"- Spatial alignment: {report.spatial_alignment_status}")
        lines.append(f"- Final source selected: {'Yes' if report.selected_sources else 'No'}")
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
    adapter = adapter or PyForestScanAdapter(execution_mode="pbm_backend")
    if isinstance(adapter, PyForestScanAdapter) and adapter.execution_mode != "qgis_python":
        from .backend import BackendService
        BackendService().processing_engine_service().validate_runtime_token_for_launch(
            report.request.runtime_token,
            tuple(product.value for product in report.request.products),
            report.batch_folder,
        )
    if not _is_logical_spatial_report(report):
        path_blockers = selected_path_invariant(report.selected_sources, ordinary=True)
        if path_blockers:
            raise ValueError("; ".join(path_blockers))
    batch_folder = report.batch_folder if report.batch_folder.exists() else create_batch_folder(report.request.output_folder)
    scalable_plan = build_source_aware_chm_plan(report)
    scalable_products = set(report.request.products)
    if report.selected_sources and scalable_products and scalable_products <= {ProductType.CHM, ProductType.RUMPLE} and scalable_plan is not None and len(scalable_plan.work_units) > 1:
        source = report.selected_sources[0]
        job_folder = batch_folder / "polygon_jobs" / unique_polygon_job_id(source.source_type)
        context = batch_run_context(Path(source.path), job_folder, reuse_existing=True).ensure_directories()
        for child in ("inputs", "staging", "outputs", "logs", "diagnostics"):
            (job_folder / child).mkdir(parents=True, exist_ok=True)
        return _execute_source_aware_chm(report, adapter, batch_folder, context, source, scalable_plan, item_callback=item_callback)
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
    source_aware_plan=None,
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
        "processing_runtime": None if report.request.runtime_token is None else report.request.runtime_token.to_dict(),
        "source_aware_raster_plan": _source_aware_chm_plan_dict(report, source_aware_plan),
        "source_aware_chm_plan": _source_aware_chm_plan_dict(report, source_aware_plan),
        "spatial_provenance": _spatial_provenance(report),
        "plan_signature": report.plan_signature,
        "repository_identity": None if report.repository is None else report.repository.to_dict(),
        "source_selection": None if report.source_selection is None else report.source_selection.to_dict(),
        "selection_method": report.selection_method,
        "selected_source_paths": [str(source.path) for source in report.selected_sources],
        "source_alternative_detections": [item.to_dict() for item in report.source_alternative_detections],
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
                "zmin": source.zmin,
                "zmax": source.zmax,
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
    if report.request.runtime_token is not None:
        validate_polygon_execution_manifest(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_polygon_source_resolution(report, folder)
    _write_effective_spatial_trace(report, folder)
    return path


def validate_polygon_execution_manifest(payload: dict[str, object]) -> None:
    """Reject manifests that cannot bind execution to runtime and spatial identity."""
    missing: list[str] = []
    runtime = payload.get("processing_runtime")
    required_runtime = ("engine_id", "executable", "environment_fingerprint", "contract_hash", "protocol", "backend_runner_hash", "dependency_manifest_hash", "product_capability_hash", "plugin_build_id")
    if not isinstance(runtime, dict):
        missing.append("processing_runtime")
    else:
        missing.extend(f"processing_runtime.{field}" for field in required_runtime if not runtime.get(field))
    if not payload.get("selected_source_paths"):
        missing.append("selected_source_paths")
    if not payload.get("plan_signature"):
        missing.append("plan_signature")
    execution_plan = payload.get("execution_plan")
    if not isinstance(execution_plan, dict) or not execution_plan.get("products"):
        missing.append("execution_plan.products")
    polygon_context = None if not isinstance(execution_plan, dict) else execution_plan.get("polygon_context")
    if not isinstance(polygon_context, dict) or not polygon_context.get("processing_geometry"):
        missing.append("execution_plan.polygon_context.processing_geometry")
    source_plan = payload.get("source_aware_raster_plan")
    if isinstance(source_plan, dict):
        ids = [str(item.get("work_unit_id", "")) for item in source_plan.get("work_units", ()) if isinstance(item, dict)]
        if not ids or any(not item for item in ids):
            missing.append("source_aware_raster_plan.work_unit_id")
        elif len(ids) != len(set(ids)):
            missing.append("source_aware_raster_plan.unique_work_unit_id")
    if missing:
        raise ValueError("POLYGON_EXECUTION_MANIFEST_INVALID: missing or invalid " + ", ".join(missing))


def _report_spatial_contexts(report: PolygonBatchPreflightReport):
    if report.source_selection is not None and report.source_selection.spatial_contexts:
        return report.source_selection.spatial_contexts
    if report.direct_selection is not None:
        return report.direct_selection.spatial_contexts
    return ()


def _spatial_provenance(report: PolygonBatchPreflightReport) -> dict[str, object]:
    contexts = _report_spatial_contexts(report)
    context = contexts[0] if contexts else None
    polygon_crs = report.request.polygon.processing_crs or report.request.polygon.source_crs
    return {
        "SOURCE_CRS_EMBEDDED": bool(context and context.raw_crs),
        "SOURCE_CRS_EFFECTIVE": "" if context is None else context.effective_crs,
        "SOURCE_CRS_BASIS": "" if context is None else context.crs_basis,
        "SOURCE_CRS_CONFIDENCE": "" if context is None else context.confidence,
        "COORDINATES_TRANSFORMED": bool(context and context.coordinates_transformed),
        "POLYGON_CRS": polygon_crs,
        "SPATIAL_FALLBACK_USED": bool(context and context.fallback_used),
    }


def _write_effective_spatial_trace(report: PolygonBatchPreflightReport, folder: Path) -> Path:
    """Write the single effective-state trace used to diagnose selection truth."""
    path = folder / "effective_spatial_trace.json"
    direct = report.direct_selection
    contexts = _report_spatial_contexts(report)
    metadata = () if direct is None else direct.metadata
    rejected = {} if direct is None else {str(item.path): item for item in direct.rejected_sources}
    selected = {str(item.path): item for item in report.selected_sources}
    sources = []
    if metadata:
        source_rows = [(item.path, item, contexts[index] if index < len(contexts) else None) for index, item in enumerate(metadata)]
    elif report.query_result is not None:
        source_rows = [(record.source_path, LidarSourceMetadata.from_catalog_record(record), contexts[index] if index < len(contexts) else None) for index, record in enumerate(report.query_result.records)]
    else:
        source_rows = []
    store = default_spatial_assignment_store()
    repository_path = Path(report.request.lidar_folder)
    for source_path, item, context in source_rows:
        rejection = rejected.get(str(source_path))
        compatibility = None if context is None else context.compatibility
        source = selected.get(str(source_path))
        sources.append({
            "path": str(source_path),
            "raw_crs": item.embedded_crs,
            "effective_crs": None if context is None else context.effective_crs,
            "effective_crs_source": None if context is None else context.provenance,
            "effective_units": None if context is None or context.units is None else context.units.value,
            "spatial_mode": None if context is None else context.mode.value,
            "polygon_crs": report.request.polygon.processing_crs or report.request.polygon.source_crs,
            "comparison_crs": report.query_geometry.catalog_crs,
            "raw_bounds": None if item.bounds is None else item.bounds.__dict__,
            "comparison_bounds": report.query_geometry.envelope.__dict__,
            "raw_coordinate_overlap": None if compatibility is None else compatibility.raw_overlap,
            "spatial_alignment": "assumed" if context and context.mode is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE else ("verified" if context and context.alignment_allowed else "blocked"),
            "final_source_selected": source is not None,
            "rejection_reason": "" if rejection is None else rejection.reason,
            **store.assignment_diagnostics(source_path, repository_path),
        })
    payload = {
        "repository_raw_crs": None if report.repository is None else getattr(report.repository, "source_spatial_reference", None),
        "repository_effective_crs": None if report.repository is None else getattr(report.repository, "source_crs", None),
        "catalog_crs": report.query_geometry.catalog_crs,
        "polygon_crs": report.request.polygon.processing_crs or report.request.polygon.source_crs,
        "processing_crs": report.query_geometry.catalog_crs,
        "output_crs": report.query_geometry.catalog_crs,
        "sources": sources,
    }
    payload["repository_raw_crs"] = None if payload["repository_raw_crs"] is None else getattr(payload["repository_raw_crs"], "crs_text", None)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _write_polygon_source_resolution(report: PolygonBatchPreflightReport, folder: Path) -> Path:
    """Persist raw/effective selection evidence without changing source metadata."""
    path = folder / "polygon_source_resolution.json"
    direct = report.direct_selection
    metadata_by_path = {} if direct is None else {str(item.path): item for item in direct.metadata}
    rejected_by_path = {} if direct is None else {str(item.path): item for item in direct.rejected_sources}
    rows = []
    candidate_paths = set(metadata_by_path) | {str(item.path) for item in report.selected_sources} | set(rejected_by_path)
    for source_path in sorted(candidate_paths):
        metadata = metadata_by_path.get(source_path)
        rejected = rejected_by_path.get(source_path)
        selected = next((item for item in report.selected_sources if str(item.path) == source_path), None)
        rows.append({
            "path": source_path,
            "raw_source_crs": None if metadata is None else metadata.embedded_crs,
            "effective_crs": selected.crs if selected is not None else (None if rejected is None else rejected.effective_crs),
            "assignment_source": "" if rejected is None else rejected.effective_crs_source,
            "polygon_crs": report.request.polygon.processing_crs or report.request.polygon.source_crs,
            "comparison_crs": report.query_geometry.catalog_crs,
            "raw_bounds": None if metadata is None or metadata.bounds is None else metadata.bounds.__dict__,
            "transformed_polygon_bounds": report.query_geometry.envelope.__dict__,
            "overlap": selected is not None,
            "reason": "selected" if selected is not None else ("not inspected" if rejected is None else rejected.reason),
            "reason_code": "SELECTED" if selected is not None else ("NOT_INSPECTED" if rejected is None else rejected.reason_code),
        })
    path.write_text(json.dumps({"repository": str(report.request.lidar_folder), "sources": rows}, indent=2), encoding="utf-8")
    return path



def build_source_aware_chm_plan(report: PolygonBatchPreflightReport):
    """Build the bounded CHM plan used by prerun, manifests, and the future executor."""
    if not ({ProductType.CHM, ProductType.RUMPLE} & set(report.request.products)) or not report.selected_sources:
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
        available_memory_bytes=__import__("pyforestscan_qgis.core.adaptive_processing",fromlist=["available_memory_bytes"]).available_memory_bytes(),
        cpu_count=max(1, os.cpu_count() or _shared_options(report).worker_count),
        profile="recommended",
        polygon_wkt=report.query_geometry.exact_polygon_wkt,
    )

def _source_aware_chm_plan_dict(report: PolygonBatchPreflightReport, plan=None):
    """Serialize the supplied frozen plan, building only during preflight."""
    if plan is None:
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


def _probe_pbm_backend(probe: Callable[[], tuple[bool, str]] | None, products: tuple[str, ...]) -> tuple[bool, str, ProcessingRuntimeToken | None]:
    if probe is not None:
        try:
            result = probe()
            ready, message = result[:2]
            token = result[2] if len(result) > 2 else None
            return bool(ready), str(message), token
        except Exception as exc:  # noqa: BLE001 - preflight should explain probe failure.
            return False, f"PBM backend check failed: {exc}", None
    try:
        from .backend import BackendService
        service = BackendService().processing_engine_service()
        token = service.runtime_token_for(products)
        return True, "Processing Engine is ready.", token
    except Exception as exc:  # noqa: BLE001
        return False, f"Processing Engine check failed: {exc}", None


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
    scalable_products = set(report.request.products)
    if scalable_products and scalable_products <= {ProductType.CHM, ProductType.RUMPLE} and scalable_plan is not None and len(scalable_plan.work_units) > 1:
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
        if ProductType.RUMPLE in report.request.products and not failures:
            rumple_path=next((path for path in outputs if Path(path).stem.lower()=="rumple"),None)
            if rumple_path is not None:
                totals=raster_totals(rumple_path)
                try:
                    summary=write_rumple_summary(context.outputs_dir/"rumple_summary.csv",totals,valid_primary=rumple_path,method="planar-area-weighted exact polygon masked raster");outputs.append(summary)
                except OSError as exc:
                    message=f"{message} Rumple raster is valid, but the secondary scalar summary could not be written: {exc}"
                    write_recent_error(context.run_folder,DurableErrorRecord("RUMPLE_SUMMARY_WRITE_FAILED","OUTPUT","Rumple completed with a warning.",str(exc),"secondary_output",job_id="polygon-logical",product="rumple",recommended_action="Use the Rumple raster; retry summary registration from diagnostics if needed."))
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
    result = _register_polygon_outputs_recoverably(result, report, mask_results, context.run_folder)
    write_polygon_batch_manifest(report, [{"source": str(source.path), "clipped": "native", "points": str(source.point_count or "unknown"), "bounds_used": str(report.query_geometry.ept_bounds), "job_folder": str(context.run_folder)}], batch_folder=batch_folder, mask_records=[_mask_record(item) for item in mask_results])
    if item_callback is not None:
        item_callback(item)
    return write_batch_summaries(result)



def _submit_and_observe_source_aware_chm(report,adapter,batch_folder,context,source,plan,*,item_callback=None):
    job_dir=context.run_folder/"coordinator";job_dir.mkdir(parents=True,exist_ok=True)
    job_id=report.plan_signature or getattr(report.execution_plan,"plan_signature","") or context.run_folder.name;attempt_id=f"attempt-{int(time.time())}"
    payload={"job_id":job_id,"attempt_id":attempt_id,"job_dir":str(job_dir),"report":report,"batch_folder":str(batch_folder),"context":context,"source":source,"plan":plan}
    payload_path=job_dir/"polygon_job_payload.pkl";temporary=payload_path.with_suffix(".partial")
    with temporary.open("wb") as stream:pickle.dump(payload,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,payload_path)
    service=adapter._backend_service()
    runtime_token=report.request.runtime_token
    if runtime_token is None:raise RuntimeError("ENGINE_RUNTIME_TOKEN_MISSING: Runtime token missing from polygon request.")
    products=tuple(product.value for product in report.request.products)
    from .atomic_state import atomic_write_json
    atomic_write_json(job_dir/"frozen_execution_plan.json", {
        "schema": "pyforestscan-frozen-polygon-plan-v1",
        "job_id": job_id,
        "attempt_id": attempt_id,
        "plan_signature": plan.plan_signature,
        "source_plan": plan.to_dict(),
        "processing_runtime": runtime_token.to_dict(),
        "products": list(products),
        "polygon_wkt": report.query_geometry.exact_polygon_wkt,
    })
    pid,_command=service.submit_polygon_coordinator(payload_path,job_dir,runtime_token,products)
    atomic_write_json(job_dir/"submission.json",{"job_id":job_id,"attempt_id":attempt_id,"coordinator_pid":pid,"payload":str(payload_path),"submitted_at":datetime.now(timezone.utc).isoformat()})
    terminal=job_dir/"terminal_result.json";last_stage=""
    while not terminal.exists():
        progress=job_dir/"progress_snapshot.json"
        if progress.exists() and item_callback is not None:
            try:
                data=json.loads(progress.read_text(encoding="utf-8"));stage=str(data.get("current_stage") or "Processing")
                if stage!=last_stage:
                    _emit_polygon_stage(item_callback,source,context,stage,str(data.get("current_activity") or "Background processing continues."));last_stage=stage
            except (OSError,ValueError):pass
        time.sleep(1)
    state=json.loads(terminal.read_text(encoding="utf-8"))
    if state.get("state")!="complete":
        from .finalization_recovery import recover_completed_polygon_job
        recovery = recover_completed_polygon_job(
            context.run_folder,
            batch_folder=batch_folder,
            job_id=job_id,
            attempt_id=attempt_id,
            required_work_unit_ids=(unit.work_unit_id for unit in plan.work_units),
            requested_products=products,
            plan_signature=plan.plan_signature,
        )
        if recovery.recovered:
            now=datetime.now(timezone.utc).isoformat()
            item=BatchItemResult(Path(source.path),context,"completed",recovery.message,recovery.outputs,_requested_extent_summary(report))
            result=BatchResult("polygon-source-aware-chm",report.request.title,now,now,Path(batch_folder),(item,),Path(batch_folder)/"batch_summary.json",Path(batch_folder)/"batch_summary.csv",Path(batch_folder)/"batch_summary.html",load_outputs_after_completion=_shared_options(report).load_outputs_after_completion,output_registry_path=recovery.registry_path)
            if item_callback is not None:_emit_polygon_stage(item_callback,source,context,"Complete with warning",recovery.message)
            return write_batch_summaries(result)
        raise RuntimeError(state.get("error") or recovery.message or "Durable polygon coordinator failed.")
    result_path=Path(state["result_path"])
    with result_path.open("rb") as stream:return pickle.load(stream)

def _execute_source_aware_chm(report, adapter, batch_folder, context, source, plan, *, item_callback=None):
    """Execute bounded shared CHM and optional Rumple through the durable coordinator."""
    if os.environ.get("PYFORESTSCAN_POLYGON_COORDINATOR")!="1" and adapter.selected_execution_backend()=="pbm_backend":
        return _submit_and_observe_source_aware_chm(report,adapter,batch_folder,context,source,plan,item_callback=item_callback)
    started_at = datetime.now(timezone.utc).isoformat()
    signature = report.plan_signature or getattr(report.execution_plan, "plan_signature", "") or "source-aware-chm"
    from .job_recovery import reconcile_polygon_job
    recovery=reconcile_polygon_job(context.run_folder / "work_units",plan,signature,expected_hag_method_signature=hag_method_signature("existing_normalized_height","HeightAboveGround"))
    if recovery.recovered_complete and item_callback is not None:
        _emit_polygon_stage(item_callback,source,context,"Recovering completed work",recovery.message)
        _emit_polygon_stage(item_callback,source,context,"Processing remaining areas","Continuing all required unfinished processing areas automatically.")
    checkpoint = CheckpointStore(context.run_folder / "work_units", signature)
    requested = set(report.request.products)
    rumple_requested = ProductType.RUMPLE in requested
    rumple_grid = derive_rumple_grid(plan.grid) if rumple_requested else None
    for skipped in plan.skipped_work_units:
        checkpoint.save_state(skipped.work_unit_id,"SkippedOutsidePolygon",{"reason_code":"OUTSIDE_EXACT_POLYGON","polygon_intersection_area":skipped.polygon_intersection_area,"polygon_coverage_percent":skipped.polygon_coverage_percent,"buffered_polygon_intersects":skipped.buffered_polygon_intersects,"source_coverage_expectation":skipped.source_coverage_expectation,"output_required":False,"work_unit":{"core_extent":skipped.core_extent.__dict__,"read_extent":skipped.read_extent.__dict__}})

    prepared_input, prepared_dimensions, preparation_status = _prepare_source_dependency(report, source, plan, context, item_callback)
    _assert_source_preparation_complete(preparation_status, prepared_input)

    def execute_unit(unit, attempt):
        unit_started=time.monotonic();timing={"schema":"pyforestscan-work-unit-timing-v1","work_unit_id":unit.work_unit_id,"attempt":attempt,"source_format":Path(prepared_input).suffix.lower(),"prepared_source":str(prepared_input),"prepared_source_size_bytes":Path(prepared_input).stat().st_size if Path(prepared_input).is_file() else None}
        unit_folder = context.run_folder / "work_units" / unit.work_unit_id
        buffered_path = unit_folder / "outputs" / "chm_buffered.tif"
        core_path = unit_folder / "outputs" / "chm_core.tif"
        buffered_path.parent.mkdir(parents=True, exist_ok=True)
        _assert_source_preparation_complete(preparation_status, prepared_input)
        request = _logical_product_request(ProductType.CHM, prepared_input, buffered_path, report)
        read = unit.read_extent
        request = replace(request, bounds=EptBounds.from_value(((read.xmin, read.xmax), (read.ymin, read.ymax)), crs=report.query_geometry.catalog_crs).to_json())
        request = replace(request,crop_polygon=None,crop_polygon_path=None,polygon_execution_input=None,source_dimensions=prepared_dimensions,source_point_count=None,work_unit_id=unit.work_unit_id,attempt_id=f"attempt-{attempt}",completed_count=max(0,unit.execution_order-1),total_count=len(plan.work_units),inspect_hag_suitability=True,hag_method="existing_normalized_height",hag_source_dimension="HeightAboveGround",hag_method_signature=hag_method_signature("existing_normalized_height","HeightAboveGround"),diagnostics_path=unit_folder/"diagnostics",polygon_intersection_area=unit.polygon_intersection_area,polygon_coverage_percent=unit.polygon_coverage_percent)
        from dataclasses import asdict
        from .chm_work_unit_execution import write_work_unit_diagnostic
        request_payload=asdict(request);request_payload.update({"original_source_path":str(source.path),"prepared_source_path":str(prepared_input),"preparation_status_path":str(preparation_status)})
        write_work_unit_diagnostic(request.diagnostics_path,"request.json",request_payload)
        write_work_unit_diagnostic(request.diagnostics_path,"geometry.json",{"work_unit_id":unit.work_unit_id,"core_extent":unit.core_extent.__dict__,"read_extent":unit.read_extent.__dict__,"polygon_intersection_area":unit.polygon_intersection_area,"polygon_coverage_percent":unit.polygon_coverage_percent,"grid_signature":plan.grid.grid_signature,"source_plan_signature":plan.plan_signature})
        product_checkpoint=request.diagnostics_path/"product_checkpoint.json"
        reusable=_load_reusable_chm(product_checkpoint,plan.plan_signature,unit.work_unit_id)
        if reusable:
            buffered_path,core_path=reusable
            timing["checkpoint_reuse_seconds"]=time.monotonic()-unit_started
        else:
            try:
                backend_started=time.monotonic()
                result = _run_logical_product(adapter, ProductType.CHM, request)
                timing["bounded_read_and_chm_seconds"]=time.monotonic()-backend_started
            except Exception as exc:
                if "empty point" not in str(exc).lower() and "no point" not in str(exc).lower():raise
                from .empty_spatial_read import classify_empty_spatial_read
                decision=classify_empty_spatial_read(core_intersection_area=unit.polygon_intersection_area,source_coverage_expected=True,read_completed=True)
                write_work_unit_diagnostic(request.diagnostics_path,"empty_read_classification.json",decision.__dict__)
                if decision.status=="CompleteNoData":
                    write_work_unit_diagnostic(request.diagnostics_path,"result.json",{"status":"CompleteNoData","reason_code":decision.reason_code,"message":decision.message})
                    return WorkUnitResult(unit.work_unit_id,"CompleteNoData",attempt_count=attempt,message=decision.message,metrics={"reason_code":decision.reason_code,"polygon_intersection_area":unit.polygon_intersection_area,"polygon_coverage_percent":unit.polygon_coverage_percent,"output_required":False,"grid_signature":plan.grid.grid_signature,"source_plan_signature":plan.plan_signature})
                error=RuntimeError(decision.message);error.code="FAILED_EMPTY_READ";raise error
            buffered_path=Path(result.output_path);core_started=time.monotonic();_extract_core_raster(buffered_path,core_path,unit.core_extent);timing["chm_core_extraction_seconds"]=time.monotonic()-core_started
            checksum_started=time.monotonic()
            _write_product_checkpoint(product_checkpoint,{"job_signature":plan.plan_signature,"work_unit_id":unit.work_unit_id,"products":{"chm":{"role":"requested" if ProductType.CHM in requested else "supporting","status":"Complete","buffered_path":str(buffered_path),"buffered_checksum":_file_checksum(buffered_path),"core_path":str(core_path),"core_checksum":_file_checksum(core_path),"grid_signature":plan.grid.grid_signature,"hag_method_signature":request.hag_method_signature}}})
            timing["chm_checksum_and_checkpoint_seconds"]=time.monotonic()-checksum_started
        metrics={"core_extent":unit.core_extent.__dict__,"read_extent":unit.read_extent.__dict__,"chm_core":str(core_path),"chm_checksum":_file_checksum(core_path),"hag_method":request.hag_method,"hag_source_dimension":request.hag_source_dimension,"hag_method_signature":request.hag_method_signature,"point_crop_policy":"buffered_rectangle_then_final_mask","polygon_intersection_area":unit.polygon_intersection_area,"polygon_coverage_percent":unit.polygon_coverage_percent,"grid_signature":plan.grid.grid_signature,"source_plan_signature":plan.plan_signature,"product_states":{"chm":"requested_complete" if ProductType.CHM in requested else "supporting_complete"}}
        primary_path=core_path;rumple_path=None
        if rumple_requested:
            rumple_started=time.monotonic()
            rumple_buffered=unit_folder/"outputs"/"rumple_buffered.tif";rumple_path=unit_folder/"outputs"/"rumple_core.tif"
            create_rumple_raster_from_chm(buffered_path,rumple_buffered,min_height=getattr(report.request.settings,"rumple_min_height",None))
            extent=rumple_core_extent(unit.core_extent,rumple_grid)
            if extent is not None:
                _extract_core_raster(rumple_buffered,rumple_path,extent);totals=raster_totals(rumple_path)
                metrics.update({"rumple_core":str(rumple_path),"rumple_checksum":_file_checksum(rumple_path),"rumple_grid_signature":rumple_grid.grid_signature,"rumple_method":"pyforestscan_qgis_patch_surface_v1","min_height":getattr(report.request.settings,"rumple_min_height",None),"surface_area_sum":totals.surface_area_sum,"planar_area_sum":totals.planar_area_sum,"valid_patch_count":totals.valid_patch_count,"product_states":{**metrics["product_states"],"rumple":"requested_complete"}});primary_path=rumple_path
                _merge_product_checkpoint(product_checkpoint,"rumple",{"role":"requested","status":"Complete","core_path":str(rumple_path),"core_checksum":metrics["rumple_checksum"],"grid_signature":rumple_grid.grid_signature,"method":metrics["rumple_method"],"min_height":metrics["min_height"],"resolution":rumple_grid.resolution,"surface_area_sum":totals.surface_area_sum,"planar_area_sum":totals.planar_area_sum,"valid_patch_count":totals.valid_patch_count})
            timing["rumple_from_chm_seconds"]=time.monotonic()-rumple_started
        timing["total_seconds"]=time.monotonic()-unit_started
        timing["rumple_lidar_reads"]=0
        bounded_read_result=request.diagnostics_path/"bounded_read_result.json"
        if bounded_read_result.is_file():
            try:timing["points_read"]=int(json.loads(bounded_read_result.read_text(encoding="utf-8")).get("point_count",0))
            except (OSError,ValueError,TypeError):pass
        if timing.get("points_read") and timing["total_seconds"]>0:timing["points_per_second"]=timing["points_read"]/timing["total_seconds"]
        metrics["timing"]=dict(timing)
        write_work_unit_diagnostic(request.diagnostics_path,"work_unit_timing.json",timing)
        write_work_unit_diagnostic(request.diagnostics_path,"result.json",{"status":"Complete","buffered_output":str(buffered_path),"chm_core":str(core_path),"rumple_core":str(rumple_path) if rumple_path else "","executed_method":request.hag_method,"metrics":metrics})
        return WorkUnitResult(unit.work_unit_id,"Complete",primary_path,attempt_count=attempt,metrics=metrics)

    def progress(event):
        if item_callback is None:
            return
        message = event.message
        if event.stop_reason:message += f" {event.stop_reason}"
        _emit_polygon_stage(item_callback, source, context, event.stage, message)

    if plan.pilot_required and plan.work_units:
        _emit_polygon_stage(item_callback, source, context, "Canary Validation", f"Validating Processing Engine and source access on {plan.work_units[0].work_unit_id} before automatic continuation.")
        canary = PolygonProductWorkScheduler((plan.work_units[0],), execute_unit, checkpoint, concurrency=1, retry_count=2, transient=_transient_work_unit_error, progress_callback=progress)
        canary_results = canary.run()
        from .atomic_state import atomic_write_json
        canary_timing=dict(canary_results[0].metrics.get("timing",{}))
        atomic_write_json(context.run_folder / "canary_result.json", {"work_unit_id": plan.work_units[0].work_unit_id, "status": canary_results[0].status, "message": canary_results[0].message, "continues_automatically": canary_results[0].status in {"Complete", "CompleteNoData"}, "timing": canary_timing, "adaptive_recommendation": {"remaining_unit_strategy": "retain_frozen_grid", "concurrency": plan.concurrency_limit, "reason": "The pilot passed; timing is persisted for future source-signature planning without mutating the active frozen plan."}})
        if canary_results[0].status not in {"Complete", "CompleteNoData"}:
            scheduler = canary
            results = (*canary_results, *(WorkUnitResult(unit.work_unit_id, "Pending", message="Canary validation did not pass; full execution was not started.") for unit in plan.work_units[1:]))
        else:
            _emit_polygon_stage(item_callback, source, context, "Processing remaining areas", "Canary passed; continuing the full job automatically.")
            scheduler = PolygonProductWorkScheduler(plan.work_units, execute_unit, checkpoint, concurrency=plan.concurrency_limit, retry_count=2, transient=_transient_work_unit_error, progress_callback=progress)
            results = scheduler.run()
    else:
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
        completion_warning = ""
        chm_paths=tuple(Path(item.metrics.get("chm_core",item.output_path)) for item in results if item.status=="Complete" and (item.metrics.get("chm_core") or item.output_path))
        if chm_paths:_mosaic_core_rasters(chm_paths, final_unmasked, plan)
        else:_create_empty_aligned_raster(final_unmasked,plan)
        if ProductType.CHM in requested:
            final_path=context.outputs_dir/"chm.tif";final_path.parent.mkdir(parents=True,exist_ok=True);final_unmasked.replace(final_path);outputs.append(final_path)
        if rumple_requested:
            rumple_paths=_verified_rumple_core_paths(results,rumple_grid,plan.plan_signature)
            rumple_plan=replace(plan,grid=AlignedRasterGrid(rumple_grid.crs,rumple_grid.resolution,rumple_grid.extent.xmin,rumple_grid.extent.ymin,rumple_grid.extent,rumple_grid.rows,rumple_grid.columns,rumple_grid.nodata),product="rumple")
            rumple_unmasked=context.run_folder/"mosaics"/"rumple.tif"
            if rumple_paths:_mosaic_core_rasters(rumple_paths,rumple_unmasked,rumple_plan)
            else:_create_empty_aligned_raster(rumple_unmasked,rumple_plan)
            rumple_final=context.outputs_dir/"rumple.tif";rumple_unmasked.replace(rumple_final);outputs.append(rumple_final)
        mask_results = _mask_paths(outputs, report)
        failures = [item for item in mask_results if item.status == "failed"]
        status = "failed" if failures else "completed"
        if rumple_requested and not failures:
            final_totals=raster_totals(context.outputs_dir/"rumple.tif")
            try:
                outputs.append(write_rumple_summary(context.outputs_dir/"rumple_summary.csv",final_totals,valid_primary=context.outputs_dir/"rumple.tif"))
            except OSError as exc:
                completion_warning=f"Processing completed with warning: the Rumple raster is valid, but its secondary scalar summary could not be written: {exc}"
                write_recent_error(context.run_folder,DurableErrorRecord("RUMPLE_SUMMARY_WRITE_FAILED","OUTPUT","Rumple completed with a warning.",str(exc),"secondary_output",job_id=signature,product="rumple",recommended_action="Use the Rumple raster; retry summary registration from diagnostics if needed."))
        nodata_count=sum(item.status=="CompleteNoData" for item in results)
        message = "; ".join(item.message for item in failures) if failures else (completion_warning or ("Processing completed. Areas without LiDAR returns are represented as NoData." if nodata_count else f"Source-aware CHM completed from {len(results)} verified required work units."))
    item = BatchItemResult(Path(source.path), context, status, message, tuple(outputs), _requested_extent_summary(report))
    result = BatchResult("polygon-source-aware-chm", report.request.title, started_at, datetime.now(timezone.utc).isoformat(), batch_folder, (item,), batch_folder / "batch_summary.json", batch_folder / "batch_summary.csv", batch_folder / "batch_summary.html", load_outputs_after_completion=_shared_options(report).load_outputs_after_completion)
    result = _register_polygon_outputs_recoverably(result, report, mask_results, context.run_folder)
    write_polygon_batch_manifest(report, [{"source": str(source.path), "strategy": "bounded_work_units", "work_units": str(len(plan.work_units)), "job_folder": str(context.run_folder)}], batch_folder=batch_folder, mask_records=[_mask_record(x) for x in mask_results], source_aware_plan=plan)
    if item_callback is not None: item_callback(item)
    return write_batch_summaries(result)


def _prepare_source_dependency(report, source, plan, context, item_callback):
    """Resolve one durable prepared source before the tiled scheduler is created."""
    from types import SimpleNamespace
    from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import prepare_durable_source
    from .source_coordinate_units import assess_processing_coordinate_units

    extents = [unit.read_extent for unit in plan.work_units]
    if not extents:
        raise RuntimeError("SOURCE_PREPARATION_FAILED: no required work-unit support extent exists.")
    support = {
        "xmin": min(item.xmin for item in extents),
        "ymin": min(item.ymin for item in extents),
        "xmax": max(item.xmax for item in extents),
        "ymax": max(item.ymax for item in extents),
    }
    source_id = hashlib.sha256(str(source.path).encode("utf-8")).hexdigest()[:12]
    status_root = context.run_folder / "source_preparation" / source_id
    base_request = _logical_product_request(ProductType.CHM, source.path, status_root / "supporting_chm.tif", report)
    crs = report.query_geometry.catalog_crs or report.request.polygon.processing_crs
    units = assess_processing_coordinate_units(crs, "", "EFFECTIVE_CRS")
    base_request = replace(
        base_request,
        bounds=None,
        crop_polygon=None,
        crop_polygon_path=None,
        polygon_execution_input=None,
        source_point_count=source.point_count,
        source_coordinate_units=units.units.value,
        source_units_basis=units.unit_basis,
        source_units_authoritative=units.authoritative,
    )
    token = report.request.runtime_token
    runtime_contract = {} if token is None else {
        "engine_id": token.engine_id,
        "contract_hash": token.contract_hash,
        "protocol": token.protocol,
        "backend_runner_hash": token.backend_runner_hash,
        "plugin_build_id": token.plugin_build_id,
        "dependency_manifest_hash": token.dependency_manifest_hash,
    }
    spec = SimpleNamespace(product="chm", requested_products=tuple(product.value for product in report.request.products), run_folder=status_root, job_id=f"{context.run_folder.name}:{source_id}")

    def preparation_progress(message):
        stage = "Validating Preparation" if "Validating" in message else "Assessing Source" if "Assess" in message or "Inspect" in message else "Resolving Height Data" if "Ground" in message else "Preparing Heights"
        _emit_polygon_stage(item_callback, source, context, stage, message)

    normalized_z_candidate = source.zmin is not None and source.zmax is not None and -100.0 <= float(source.zmin) < float(source.zmax) <= 150.0 and float(source.zmax) - float(source.zmin) >= 2.0
    result = prepare_durable_source(
        spec,
        base_request,
        status_root=status_root,
        preparation_bounds=support,
        normalized_z_candidate=normalized_z_candidate,
        runtime_contract=runtime_contract,
        progress=preparation_progress,
    )
    status_path = status_root / "status.json"
    if result is None:
        prepared_path = Path(source.path)
        dimensions = ("X", "Y", "Z", "HeightAboveGround")
    else:
        prepared_path = Path(result.request.input_path)
        dimensions = tuple(result.request.source_dimensions)
    _emit_polygon_stage(item_callback, source, context, "Preparation Complete", f"Prepared source is ready for {len(plan.work_units)} required work areas.")
    return prepared_path, dimensions, status_path


def _assert_source_preparation_complete(status_path: Path, prepared_path: Path) -> None:
    try:
        payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("SOURCE_PREPARATION_ARTIFACT_MISSING: durable source preparation status is unavailable.") from exc
    if payload.get("state") != "COMPLETE":
        raise RuntimeError(f"SOURCE_PREPARATION_FAILED: expected COMPLETE, observed {payload.get('state', 'MISSING')}.")
    if not Path(prepared_path).is_file():
        raise RuntimeError(f"SOURCE_PREPARATION_ARTIFACT_MISSING: {prepared_path}")
    expected = str(payload.get("preparation_artifact_path") or "")
    if expected and Path(expected) != Path(prepared_path):
        raise RuntimeError(f"SOURCE_PREPARATION_SIGNATURE_MISMATCH: status references {expected}; worker received {prepared_path}.")

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


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_product_checkpoint(path: Path, payload: dict) -> None:
    from .atomic_state import atomic_write_json

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def _merge_product_checkpoint(path: Path, product: str, payload: dict) -> None:
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {}
    products = dict(current.get("products") or {})
    products[product] = payload
    current["products"] = products
    _write_product_checkpoint(path, current)


def _load_reusable_chm(path: Path, expected_signature: str, work_unit_id: str):
    """Return verified CHM products from an interrupted Rumple attempt."""
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        chm = checkpoint["products"]["chm"]
        buffered = Path(chm["buffered_path"])
        core = Path(chm["core_path"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if checkpoint.get("job_signature") != expected_signature or checkpoint.get("work_unit_id") != work_unit_id:
        return None
    if chm.get("status") != "Complete" or not buffered.is_file() or not core.is_file():
        return None
    if chm.get("buffered_checksum") != _file_checksum(buffered) or chm.get("core_checksum") != _file_checksum(core):
        return None
    return buffered, core


def _verified_rumple_core_paths(results, rumple_grid, expected_signature: str) -> tuple[Path, ...]:
    """Select only complete Rumple cores that match the current product plan."""
    verified = []
    for result in results:
        if result.status != "Complete":
            continue
        metrics = result.metrics or {}
        raw_path = metrics.get("rumple_core")
        path = Path(raw_path) if raw_path else None
        if not path or not path.is_file():
            raise RuntimeError(f"Completed work unit {result.work_unit_id} has no Rumple core raster.")
        if metrics.get("source_plan_signature") != expected_signature:
            raise RuntimeError(f"Rumple work unit {result.work_unit_id} belongs to a different execution plan.")
        if metrics.get("rumple_grid_signature") != rumple_grid.grid_signature:
            raise RuntimeError(f"Rumple work unit {result.work_unit_id} uses an incompatible raster grid.")
        if metrics.get("rumple_method") != "pyforestscan_qgis_patch_surface_v1":
            raise RuntimeError(f"Rumple work unit {result.work_unit_id} uses an unsupported method.")
        if metrics.get("rumple_checksum") != _file_checksum(path):
            raise RuntimeError(f"Rumple work unit {result.work_unit_id} failed checksum verification.")
        verified.append(path)
    return tuple(verified)

def _mosaic_core_rasters(paths, output_path: Path, plan) -> None:
    if not paths or any(path is None or not Path(path).is_file() for path in paths):
        raise RuntimeError("CHM mosaic requires at least one verified required-core raster.")
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

def _create_empty_aligned_raster(output_path: Path,plan) -> None:
    try:
        from osgeo import gdal,osr
    except ImportError as exc:
        raise RuntimeError("GDAL is required to create an aligned NoData CHM raster.") from exc
    output_path.parent.mkdir(parents=True,exist_ok=True);temporary=output_path.with_suffix(".partial.tif")
    dataset=gdal.GetDriverByName("GTiff").Create(str(temporary),plan.grid.columns,plan.grid.rows,1,gdal.GDT_Float32,options=("TILED=YES","COMPRESS=DEFLATE"))
    if dataset is None:raise RuntimeError("Aligned NoData CHM creation failed.")
    dataset.SetGeoTransform((plan.grid.origin_x,plan.grid.resolution,0.0,plan.grid.total_extent.ymax,0.0,-plan.grid.resolution))
    reference=osr.SpatialReference();reference.SetFromUserInput(plan.grid.crs);dataset.SetProjection(reference.ExportToWkt())
    band=dataset.GetRasterBand(1);band.SetNoDataValue(plan.grid.nodata);band.Fill(plan.grid.nodata);band.FlushCache();dataset=None;temporary.replace(output_path)

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
        ProductType.RUMPLE: "rumple.tif",
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


def _register_polygon_outputs_recoverably(result: BatchResult, report: PolygonBatchPreflightReport, mask_results: tuple[RasterMaskResult, ...], job_folder: Path) -> BatchResult:
    """Preserve verified primary products when only final registration fails."""
    try:
        return _register_polygon_outputs(result, report, mask_results)
    except Exception as exc:  # noqa: BLE001 - registry recovery must not rerun scientific work.
        write_recent_error(job_folder,DurableErrorRecord("OUTPUT_REGISTRATION_FAILED","OUTPUT","Outputs were created but registration needs repair.",str(exc),"registration",job_id=result.batch_id,recommended_action="Open the job diagnostics and retry output registration without recomputing products."))
        items=tuple(replace(item,message=f"{item.message} Output registration requires recovery; generated files were preserved.") if item.status=="completed" else item for item in result.items)
        return replace(result,items=items)


def _product_key_from_output(path: Path) -> str:
    stem = path.stem.lower()
    if "rumple" in stem and path.suffix.lower()==".csv":
        return "rumple_summary"
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
