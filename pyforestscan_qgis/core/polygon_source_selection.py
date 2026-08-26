"""Authoritative polygon repository resolution and source selection."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .crs_alignment import SpatialAlignmentResult, align_polygon_to_crs
from .ept_repository import repair_ept_crs_catalog_state, resolve_ept_selection
from .ept_spatial_reference import ResolvedSpatialReference, ept_spatial_metadata_summary, is_incomplete_crs_identifier, resolve_ept_spatial_reference
from .lidar_catalog_models import LidarCatalogQuery, LidarCatalogQueryResult, PolygonQueryGeometry, WorkloadEstimate, default_lidar_catalog_path
from .lidar_catalog_integrity import inspect_catalog_integrity
from .lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from .lidar_inventory import LidarSourceRecord
from .lidar_source_metadata import LidarSourceMetadata
from .polygon_source import NormalizedPolygonSelection
from .effective_source_spatial_profile import resolve_effective_source_spatial_profile
from .processing_spatial_context import EffectiveSpatialContext, EffectiveSpatialMode, SourceLocalFallbackPolicy, default_source_local_policy_store
from .spatial_selection import Bounds2D


@dataclass(frozen=True)
class SpatialEnvelope:
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    crs: str

    @classmethod
    def from_bounds(cls, bounds: Bounds2D, crs: str) -> "SpatialEnvelope":
        return cls(bounds.xmin, bounds.xmax, bounds.ymin, bounds.ymax, crs)

    def to_bounds(self) -> Bounds2D:
        return Bounds2D(self.xmin, self.ymin, self.xmax, self.ymax)

    def intersects(self, other: "SpatialEnvelope") -> bool:
        if _norm_crs(self.crs) != _norm_crs(other.crs):
            raise ValueError(f"CRS mismatch: cannot compare {self.crs or 'unknown'} to {other.crs or 'unknown'}.")
        return self.to_bounds().intersects(other.to_bounds())

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class PolygonNormalizationReport:
    source_feature_count: int
    original_geometry_type: str
    normalized_geometry_type: str
    original_valid: bool
    repaired: bool
    dissolved: bool
    multipart: bool
    holes: int
    vertex_count: int
    original_area: float
    normalized_area: float
    area_change_percent: float
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class PolygonSpatialContext:
    original_geometry: str
    original_crs: str
    normalized_geometry: str
    processing_geometry: str
    processing_crs: str
    source_geometry: str
    source_crs: str
    source_envelope: SpatialEnvelope
    normalization_report: PolygonNormalizationReport

    def to_dict(self) -> dict[str, object]:
        payload = dict(self.__dict__)
        payload["source_envelope"] = self.source_envelope.to_dict()
        payload["normalization_report"] = self.normalization_report.to_dict()
        return payload


@dataclass(frozen=True)
class ResolvedLidarRepository:
    repository_id: str
    selected_path: Path
    normalized_path: Path
    repository_kind: str
    logical_source_paths: tuple[Path, ...]
    ept_json_path: Path | None = None
    copc_paths: tuple[Path, ...] = ()
    local_tile_root: Path | None = None
    catalog_path: Path | None = None
    source_crs: str | None = None
    source_extent: SpatialEnvelope | None = None
    resolution_method: str = ""
    detection_confidence: str = "low"
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    source_spatial_reference: ResolvedSpatialReference | None = None
    ept_spatial_metadata: dict[str, object] | None = None

    @property
    def crs_resolution_source(self) -> str:
        return self.source_spatial_reference.source if self.source_spatial_reference is not None else ""

    def to_dict(self) -> dict[str, object]:
        return {
            "repository_id": self.repository_id,
            "selected_path": str(self.selected_path),
            "normalized_path": str(self.normalized_path),
            "repository_kind": self.repository_kind,
            "logical_source_paths": [str(path) for path in self.logical_source_paths],
            "ept_json_path": str(self.ept_json_path) if self.ept_json_path else None,
            "copc_paths": [str(path) for path in self.copc_paths],
            "local_tile_root": str(self.local_tile_root) if self.local_tile_root else None,
            "catalog_path": str(self.catalog_path) if self.catalog_path else None,
            "source_crs": self.source_crs,
            "source_extent": None if self.source_extent is None else self.source_extent.to_dict(),
            "resolution_method": self.resolution_method,
            "detection_confidence": self.detection_confidence,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "crs_resolution_source": self.crs_resolution_source,
            "source_spatial_reference": None if self.source_spatial_reference is None else self.source_spatial_reference.to_dict(),
            "ept_spatial_metadata": self.ept_spatial_metadata,
        }


@dataclass(frozen=True)
class RejectedSource:
    path: Path
    source_kind: str
    rejection_code: str
    user_reason: str
    technical_reason: str
    source_crs: str | None = None
    source_extent: SpatialEnvelope | None = None
    query_extent: SpatialEnvelope | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "source_kind": self.source_kind,
            "rejection_code": self.rejection_code,
            "user_reason": self.user_reason,
            "technical_reason": self.technical_reason,
            "source_crs": self.source_crs,
            "source_extent": None if self.source_extent is None else self.source_extent.to_dict(),
            "query_extent": None if self.query_extent is None else self.query_extent.to_dict(),
            "details": self.details,
        }


@dataclass(frozen=True)
class PreflightMessage:
    code: str
    severity: str
    title: str
    message: str
    technical_details: str = ""
    action: str = ""
    deduplication_key: str = ""

    def to_text(self) -> str:
        return f"{self.title}: {self.message}" if self.title else self.message

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class PolygonSourceSelectionResult:
    repository_kind: str
    logical_candidates: tuple[LidarSourceRecord, ...]
    selected_sources: tuple[LidarSourceRecord, ...]
    rejected_sources: tuple[RejectedSource, ...]
    transformed_polygon: str
    transformed_envelope: SpatialEnvelope
    source_extent: SpatialEnvelope | None
    overlap_result: str
    exact_intersection_result: str
    warnings: tuple[PreflightMessage, ...]
    blockers: tuple[PreflightMessage, ...]
    timings: dict[str, float]
    query_result: LidarCatalogQueryResult | None = None
    catalog_skipped_count: int = 0
    workload_estimate: WorkloadEstimate | None = None
    spatial_alignment: SpatialAlignmentResult | None = None
    spatial_contexts: tuple[EffectiveSpatialContext, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "repository_kind": self.repository_kind,
            "logical_candidates": [_source_to_dict(item) for item in self.logical_candidates],
            "selected_sources": [_source_to_dict(item) for item in self.selected_sources],
            "rejected_sources": [item.to_dict() for item in self.rejected_sources],
            "transformed_polygon": self.transformed_polygon,
            "transformed_envelope": self.transformed_envelope.to_dict(),
            "source_extent": None if self.source_extent is None else self.source_extent.to_dict(),
            "overlap_result": self.overlap_result,
            "exact_intersection_result": self.exact_intersection_result,
            "warnings": [item.to_dict() for item in self.warnings],
            "blockers": [item.to_dict() for item in self.blockers],
            "timings": self.timings,
            "catalog_skipped_count": self.catalog_skipped_count,
            "spatial_alignment": None if self.spatial_alignment is None else self.spatial_alignment.to_dict(),
            "spatial_contexts": [item.to_dict() for item in self.spatial_contexts],
        }


@dataclass(frozen=True)
class PolygonExecutionPlan:
    repository: ResolvedLidarRepository
    polygon_context: PolygonSpatialContext
    source_selection: PolygonSourceSelectionResult
    products: tuple[str, ...]
    shared_batch_options: Any
    polygon_batch_options: Any
    requested_concurrency: int
    effective_concurrency: int
    spatial_read_plan: dict[str, object]
    masking_plan: dict[str, object]
    output_plan: dict[str, object]
    loading_plan: dict[str, object]
    workload_estimate: WorkloadEstimate | None
    warnings: tuple[PreflightMessage, ...]
    blockers: tuple[PreflightMessage, ...]
    readiness: str
    validation_results: dict[str, object]
    plan_signature: str

    def to_dict(self) -> dict[str, object]:
        return {
            "repository": self.repository.to_dict(),
            "polygon_context": self.polygon_context.to_dict(),
            "source_selection": self.source_selection.to_dict(),
            "products": list(self.products),
            "shared_batch_options": _to_dict(self.shared_batch_options),
            "polygon_batch_options": _to_dict(self.polygon_batch_options),
            "requested_concurrency": self.requested_concurrency,
            "effective_concurrency": self.effective_concurrency,
            "spatial_read_plan": self.spatial_read_plan,
            "masking_plan": self.masking_plan,
            "output_plan": self.output_plan,
            "loading_plan": self.loading_plan,
            "workload_estimate": None if self.workload_estimate is None else dict(self.workload_estimate.__dict__),
            "warnings": [item.to_dict() for item in self.warnings],
            "blockers": [item.to_dict() for item in self.blockers],
            "readiness": self.readiness,
            "validation_results": self.validation_results,
            "plan_signature": self.plan_signature,
        }


class PolygonSourceSelectionService:
    def resolve_repository(self, selected_path: Path | str, catalog_path: Path | str | None = None) -> ResolvedLidarRepository:
        selected = Path(selected_path).expanduser()
        resolved = selected.resolve() if selected.exists() else selected.absolute()
        catalog = Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(resolved)
        ept = resolve_ept_selection(resolved)
        if ept is not None:
            bounds, crs, points, resolved, payload = _read_ept_metadata(ept.ept_json)
            source_extent = SpatialEnvelope.from_bounds(bounds, crs) if bounds is not None and crs else None
            state_repair = repair_ept_crs_catalog_state(catalog, ept.ept_json) if catalog.exists() else None
            warnings = tuple(resolved.warnings)
            if state_repair is not None and state_repair.repaired:
                warnings = (*warnings, state_repair.message)
            errors = tuple(resolved.errors)
            if bounds is None:
                errors = (*errors, "EPT metadata does not provide a usable root extent.")
            if not crs:
                errors = (*errors, "The EPT coordinate system could not be determined.")
            return ResolvedLidarRepository(
                repository_id=_repo_id(ept.normalized_repository, "ept"),
                selected_path=selected,
                normalized_path=ept.normalized_repository,
                repository_kind="ept",
                logical_source_paths=(ept.ept_json,),
                ept_json_path=ept.ept_json,
                catalog_path=catalog,
                source_crs=crs,
                source_extent=source_extent,
                resolution_method=resolved.source if resolved.valid else "ept_metadata_unresolved",
                detection_confidence="high" if resolved.valid else "low",
                warnings=warnings,
                errors=tuple(dict.fromkeys(errors)),
                source_spatial_reference=resolved,
                ept_spatial_metadata=ept_spatial_metadata_summary(str(ept.ept_json), payload, resolved),
            )
        source_crs = None
        source_extent = None
        warnings: tuple[str, ...] = ()
        if catalog.exists():
            integrity = inspect_catalog_integrity(catalog, resolved)
            source_crs = integrity.repository_crs_override
            if integrity.extent_union is not None and source_crs:
                source_extent = SpatialEnvelope.from_bounds(integrity.extent_union, source_crs)
            if integrity.status == "CRS Assignment Required":
                warnings = ("Repository coordinate system assignment is required before coverage can be compared with polygons.",)
        return ResolvedLidarRepository(
            repository_id=_repo_id(resolved, "indexed_repository"),
            selected_path=selected,
            normalized_path=resolved,
            repository_kind="indexed_repository",
            logical_source_paths=(),
            local_tile_root=resolved if resolved.is_dir() else None,
            catalog_path=catalog,
            source_crs=source_crs,
            source_extent=source_extent,
            resolution_method="catalog_required",
            detection_confidence="medium" if catalog.exists() else "low",
            warnings=warnings,
            errors=(),
        )

    def select_sources(
        self,
        repository: ResolvedLidarRepository,
        polygon: NormalizedPolygonSelection,
        *,
        catalog_crs: str | None = None,
        thresholds: Any = None,
        spatial_policy: SourceLocalFallbackPolicy | None = None,
    ) -> PolygonSourceSelectionResult:
        start = time.perf_counter()
        normalization = polygon_normalization_report(polygon)
        source_crs = repository.source_crs or catalog_crs or polygon.processing_crs
        if repository.repository_kind == "ept":
            return self._select_native_ept(repository, polygon, start)
        query_geometry = derive_polygon_query_geometry(polygon, catalog_crs=source_crs)
        transformed_envelope = SpatialEnvelope.from_bounds(query_geometry.envelope, query_geometry.catalog_crs)
        polygon_context = PolygonSpatialContext(
            original_geometry=polygon.geometry_wkt,
            original_crs=polygon.source_crs,
            normalized_geometry=polygon.geometry_wkt,
            processing_geometry=polygon.geometry_wkt,
            processing_crs=polygon.processing_crs,
            source_geometry=query_geometry.exact_polygon_wkt,
            source_crs=query_geometry.catalog_crs,
            source_envelope=transformed_envelope,
            normalization_report=normalization,
        )
        setattr(self, "_last_polygon_context", polygon_context)
        query = query_catalog_for_polygon(
            repository.catalog_path or default_lidar_catalog_path(repository.normalized_path),
            repository.normalized_path,
            polygon,
            catalog_crs=source_crs,
            thresholds=thresholds,
        )
        warnings = tuple(_message("CATALOG_WARNING", "warning", "Catalog warning", item) for item in query.warnings)
        blockers: tuple[PreflightMessage, ...] = ()
        integrity_status = getattr(query, "catalog_integrity_status", "Unknown")
        if not query.records:
            if integrity_status not in {"Healthy", "Healthy with validated repository CRS override", "Healthy with effective repository assignment"}:
                blocker_text = next((item for item in query.warnings if "catalog" in item.lower() or "spatial bounds" in item.lower() or "supported" in item.lower()), "Repository catalog is not spatially usable.")
                blockers = (_message("CATALOG_NOT_SPATIALLY_USABLE", "blocker", "Catalog Needs Repair", blocker_text, "Run Inspect Repository or Repair Catalog before polygon processing.", "Repair Catalog"),)
            else:
                blockers = (_message("NO_COVERAGE", "blocker", "No LiDAR coverage", "No LiDAR coverage was found for this area."),)
        policy = spatial_policy or default_source_local_policy_store().read()
        contexts: list[EffectiveSpatialContext] = []
        effective_records: list[LidarSourceRecord] = []
        for record in query.records:
            metadata = LidarSourceMetadata.from_catalog_record(record)
            profile = resolve_effective_source_spatial_profile(
                metadata,
                repository.normalized_path,
                repository_crs_override=repository.source_crs,
                polygon_crs=polygon.processing_crs or polygon.source_crs,
                polygon_bounds=polygon.bounds,
                policy=policy,
            )
            if profile.context is not None:
                contexts.append(profile.context)
            if profile.safe_for_spatial_alignment and profile.effective_crs:
                effective_records.append(replace(record.to_source_record(), crs=profile.effective_crs))
        if query.records and not effective_records:
            blockers = (_message("SOURCE_CRS_REQUIRED", "blocker", "Coordinate system needed", "The selected LiDAR cannot be aligned safely with this polygon.", "Raw coordinate overlap is reported separately from spatial alignment.", "Use Project CRS or Choose CRS"),)
        assumed = [item for item in contexts if item.mode is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE]
        if assumed:
            warnings = (*warnings, _message("ASSUMED_MATCHING_COORDINATE_SPACE", "warning", "Spatial reference assumed", f"Using polygon coordinate system {assumed[0].effective_crs} for unreferenced LiDAR. Coordinates are unchanged."))
        return PolygonSourceSelectionResult(
            repository_kind=repository.repository_kind,
            logical_candidates=tuple(effective_records),
            selected_sources=tuple(effective_records),
            rejected_sources=(),
            transformed_polygon=query_geometry.exact_polygon_wkt,
            transformed_envelope=transformed_envelope,
            source_extent=None if getattr(query, "repository_extent", None) is None else SpatialEnvelope.from_bounds(query.repository_extent, query_geometry.catalog_crs),
            overlap_result="yes" if query.records else "no",
            exact_intersection_result="envelope",
            warnings=warnings,
            blockers=blockers,
            timings={"source_selection": time.perf_counter() - start},
            query_result=query,
            catalog_skipped_count=query.skipped_count,
            workload_estimate=query.workload_estimate,
            spatial_contexts=tuple(contexts),
        )

    @property
    def last_polygon_context(self) -> PolygonSpatialContext | None:
        return getattr(self, "_last_polygon_context", None)

    def _select_native_ept(
        self,
        repository: ResolvedLidarRepository,
        polygon: NormalizedPolygonSelection,
        start: float,
    ) -> PolygonSourceSelectionResult:
        warnings: list[PreflightMessage] = []
        blockers: list[PreflightMessage] = []
        rejected: list[RejectedSource] = []
        selected: tuple[LidarSourceRecord, ...] = ()
        source_extent = repository.source_extent
        alignment = align_polygon_to_crs(polygon, repository.source_crs)
        transformed_envelope = SpatialEnvelope.from_bounds(alignment.transformed_bounds, alignment.target_crs) if alignment.transformed_bounds is not None else SpatialEnvelope.from_bounds(polygon.bounds, polygon.processing_crs or polygon.source_crs)
        query_geometry = PolygonQueryGeometry(
            envelope=transformed_envelope.to_bounds(),
            exact_polygon_wkt=alignment.transformed_wkt,
            source_crs=alignment.original_crs,
            catalog_crs=alignment.target_crs,
            ept_bounds=transformed_envelope.to_bounds().to_ept_bounds(),
            warnings=alignment.warnings,
        )
        polygon_context = PolygonSpatialContext(
            original_geometry=polygon.geometry_wkt,
            original_crs=polygon.source_crs,
            normalized_geometry=polygon.geometry_wkt,
            processing_geometry=polygon.geometry_wkt,
            processing_crs=polygon.processing_crs,
            source_geometry=query_geometry.exact_polygon_wkt,
            source_crs=query_geometry.catalog_crs,
            source_envelope=transformed_envelope,
            normalization_report=polygon_normalization_report(polygon),
        )
        setattr(self, "_last_polygon_context", polygon_context)
        if repository.errors and not repository.source_crs:
            title = "EPT coordinate system incomplete" if any("INCOMPLETE_CRS_AUTHORITY" in item for item in repository.errors) else "EPT coordinate system unavailable"
            user_text = "The EPT coordinate-system metadata is incomplete." if title.endswith("incomplete") else "The EPT coordinate system could not be determined."
            blockers.append(_message("EPT_CRS_UNRESOLVED", "blocker", title, user_text, "; ".join(repository.errors), "Choose Coordinate System"))
        elif source_extent is None:
            blockers.append(_message("INVALID_SOURCE_EXTENT", "blocker", "EPT extent unavailable", "Repository extent could not be read from ept.json."))
        elif not alignment.ready:
            blockers.append(_message("CRS_TRANSFORM_FAILED", "blocker", "Coordinate systems need review", alignment.user_message, alignment.technical_details, "Choose Coordinate System"))
            rejected.append(RejectedSource(repository.ept_json_path or repository.normalized_path, "ept", "CRS_TRANSFORM_FAILED", "Coordinate systems could not be compared safely.", alignment.technical_details, repository.source_crs, source_extent, transformed_envelope, details={"spatial_alignment": alignment.to_dict()}))
        elif _norm_crs(transformed_envelope.crs) != _norm_crs(source_extent.crs):
            blockers.append(_message("CRS_TRANSFORM_FAILED", "blocker", "Spatial alignment unavailable", "The polygon could not be transformed into the EPT coordinate system.", f"Polygon CRS: {transformed_envelope.crs}; repository CRS: {source_extent.crs}", "Choose Coordinate System"))
            rejected.append(RejectedSource(repository.ept_json_path or repository.normalized_path, "ept", "CRS_TRANSFORM_FAILED", "Coordinate systems could not be compared safely.", "No CRS transformer was available for native EPT source selection.", repository.source_crs, source_extent, transformed_envelope))
        elif transformed_envelope.intersects(source_extent):
            if alignment.transformation_required:
                warnings.append(_message("SPATIAL_ALIGNMENT_AUTOMATIC", "warning", "Spatial alignment ready", "The polygon will be transformed automatically to match the LiDAR data.", alignment.technical_details))
            path = repository.ept_json_path or repository.logical_source_paths[0]
            size = path.stat().st_size if path.exists() else 0
            modified = path.stat().st_mtime_ns if path.exists() else 0
            selected = (LidarSourceRecord(path, "ept", int(size), int(modified), bounds=source_extent.to_bounds(), crs=repository.source_crs, point_count=None),)
            warnings.append(_message("WORKLOAD_UNAVAILABLE", "warning", "Workload estimate unavailable", "The repository does not provide a reliable polygon-subset estimate.", "Root-wide EPT point metadata is diagnostics-only for polygon subsets."))
        else:
            path = repository.ept_json_path or repository.normalized_path
            rejected.append(RejectedSource(path, "ept", "OUTSIDE_POLYGON_ENVELOPE", "The selected area is outside this EPT dataset coverage.", "Transformed polygon envelope does not intersect the EPT root extent.", repository.source_crs, source_extent, transformed_envelope))
            blockers.append(_message("NO_COVERAGE", "blocker", "No LiDAR coverage", "No LiDAR coverage was found for this area.", "Native EPT extent and transformed polygon envelope do not overlap.", "Preview Spatial Selection"))
        workload = WorkloadEstimate(
            None,
            confidence="Unavailable",
            method="Unavailable",
            polygon_area=polygon.area,
            unit_basis="source metadata only",
            assumptions=("EPT root point counts describe the whole source, not the requested polygon subset.",),
            warning="A reliable point estimate is unavailable for this EPT subset.",
            is_plausible=False,
        )
        query = LidarCatalogQuery(
            repository.catalog_path or default_lidar_catalog_path(repository.normalized_path),
            repository.normalized_path,
            transformed_envelope.to_bounds(),
            query_geometry.exact_polygon_wkt,
            transformed_envelope.crs,
        )
        result = LidarCatalogQueryResult(
            query=query,
            records=(),
            candidate_count=len(selected),
            exact_intersecting_count=len(selected),
            skipped_count=0,
            metadata_error_count=0,
            estimated_point_count=None,
            estimated_bytes=0,
            query_seconds=time.perf_counter() - start,
            warnings=tuple(item.to_text() for item in warnings),
            timing_seconds={"rtree_lookup": 0.0, "row_loading": 0.0, "workload_estimation": 0.0, "native_ept_resolution": time.perf_counter() - start, "total_preflight_query": time.perf_counter() - start},
            point_estimate_confidence="Unavailable",
            workload_estimate=workload,
        )
        return PolygonSourceSelectionResult(
            repository_kind="ept",
            logical_candidates=selected,
            selected_sources=selected,
            rejected_sources=tuple(rejected),
            transformed_polygon=query_geometry.exact_polygon_wkt,
            transformed_envelope=transformed_envelope,
            source_extent=source_extent,
            overlap_result="yes" if selected else "no",
            exact_intersection_result="envelope",
            warnings=tuple(dedupe_messages(warnings)),
            blockers=tuple(dedupe_messages(blockers)),
            timings={"source_selection": time.perf_counter() - start},
            query_result=result,
            catalog_skipped_count=0,
            workload_estimate=workload,
            spatial_alignment=alignment,
        )


def build_polygon_execution_plan(
    *,
    repository: ResolvedLidarRepository,
    polygon_context: PolygonSpatialContext,
    source_selection: PolygonSourceSelectionResult,
    products: tuple[str, ...],
    shared_batch_options: Any,
    polygon_batch_options: Any,
    requested_concurrency: int,
    effective_concurrency: int,
    output_folder: Path,
    backend_ready: bool,
    backend_message: str,
) -> PolygonExecutionPlan:
    blockers = tuple(dedupe_messages(source_selection.blockers))
    warnings = tuple(dedupe_messages(source_selection.warnings))
    readiness = "ready" if backend_ready and not blockers and bool(source_selection.selected_sources) else "blocked"
    payload = {
        "repository_id": repository.repository_id,
        "repository_crs": repository.source_crs,
        "repository_spatial_identity": repository.resolution_method,
        "polygon_hash": _hash_text(polygon_context.source_geometry),
        "polygon_crs": polygon_context.source_crs,
        "polygon_bounds": source_selection.transformed_envelope.to_dict(),
        "products": products,
        "shared_batch_options": _to_dict(shared_batch_options),
        "polygon_batch_options": _to_dict(polygon_batch_options),
        "output_folder": str(output_folder),
        "backend_ready": backend_ready,
        "backend_message": backend_message,
        "selected_source_paths": [str(source.path) for source in source_selection.selected_sources],
        "selected_source_crs": [source.crs for source in source_selection.selected_sources],
        "selected_source_bounds": [None if source.bounds is None else source.bounds.__dict__ for source in source_selection.selected_sources],
        "spatial_modes": [context.mode.value for context in source_selection.spatial_contexts],
        "spatial_provenance": [context.provenance for context in source_selection.spatial_contexts],
    }
    signature = _hash_text(json.dumps(payload, sort_keys=True, default=str))
    return PolygonExecutionPlan(
        repository=repository,
        polygon_context=polygon_context,
        source_selection=source_selection,
        products=products,
        shared_batch_options=shared_batch_options,
        polygon_batch_options=polygon_batch_options,
        requested_concurrency=requested_concurrency,
        effective_concurrency=effective_concurrency,
        spatial_read_plan={"mode": repository.repository_kind, "bounds": source_selection.transformed_envelope.to_dict(), "selected_sources": len(source_selection.selected_sources), "selected_source_paths": [str(source.path) for source in source_selection.selected_sources]},
        masking_plan={"exact_raster_mask": bool(getattr(polygon_batch_options, "exact_raster_mask", True)), "engine": getattr(polygon_batch_options, "mask_engine", "automatic")},
        output_plan={"folder": str(output_folder), "registry": "generated_outputs.json"},
        loading_plan={"load_after_completion": bool(getattr(shared_batch_options, "load_outputs_after_completion", False)), "qgis_thread": "ui"},
        workload_estimate=source_selection.workload_estimate,
        warnings=warnings,
        blockers=blockers,
        readiness=readiness,
        validation_results={"backend_ready": backend_ready, "backend_message": backend_message},
        plan_signature=signature,
    )


def polygon_normalization_report(polygon: NormalizedPolygonSelection) -> PolygonNormalizationReport:
    text = polygon.geometry_wkt.upper()
    vertex_count = max(0, len(_numbers(polygon.geometry_wkt)) // 2)
    holes = max(0, polygon.geometry_wkt.count("), ("))
    multipart = text.startswith("MULTIPOLYGON") or polygon.feature_count > 1
    return PolygonNormalizationReport(
        source_feature_count=polygon.feature_count,
        original_geometry_type=polygon.geometry_type,
        normalized_geometry_type=polygon.geometry_type,
        original_valid=True,
        repaired=any("repair" in warning.lower() for warning in polygon.warnings),
        dissolved=polygon.feature_count > 1,
        multipart=multipart,
        holes=holes,
        vertex_count=vertex_count,
        original_area=polygon.area,
        normalized_area=polygon.area,
        area_change_percent=0.0,
        warnings=polygon.warnings,
        errors=(),
    )


def dedupe_messages(messages: list[PreflightMessage] | tuple[PreflightMessage, ...]) -> tuple[PreflightMessage, ...]:
    seen: set[str] = set()
    out: list[PreflightMessage] = []
    for message in messages:
        key = message.deduplication_key or message.code or message.message
        if key in seen:
            continue
        seen.add(key)
        out.append(message)
    return tuple(out)


def _message(code: str, severity: str, title: str, message: str, technical: str = "", action: str = "") -> PreflightMessage:
    return PreflightMessage(code, severity, title, message, technical, action, code)


def _read_ept_metadata(path: Path) -> tuple[Bounds2D | None, str | None, int | None, ResolvedSpatialReference, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        empty = resolve_ept_spatial_reference(None)
        return None, None, None, empty, {}
    bounds_value = payload.get("bounds") if isinstance(payload, dict) else None
    bounds = None
    if isinstance(bounds_value, list) and len(bounds_value) >= 5:
        try:
            bounds = Bounds2D(float(bounds_value[0]), float(bounds_value[1]), float(bounds_value[3]), float(bounds_value[4]))
        except (TypeError, ValueError):
            bounds = None
    resolved = resolve_ept_spatial_reference(payload if isinstance(payload, dict) else None)
    crs = resolved.crs_text if resolved.valid and not is_incomplete_crs_identifier(resolved.crs_text) else None
    point_count = payload.get("points") if isinstance(payload, dict) else None
    try:
        count = int(point_count) if point_count is not None else None
    except (TypeError, ValueError):
        count = None
    return bounds, crs, count, resolved, payload if isinstance(payload, dict) else {}


def _source_to_dict(source: LidarSourceRecord) -> dict[str, object]:
    return {
        "path": str(source.path),
        "source_type": source.source_type,
        "size_bytes": source.size_bytes,
        "modified_ns": source.modified_ns,
        "bounds": None if source.bounds is None else source.bounds.__dict__,
        "crs": source.crs,
        "point_count": source.point_count,
    }


def _repo_id(path: Path, kind: str) -> str:
    return _hash_text(f"{kind}:{str(path).replace(chr(92), '/').lower()}")[:16]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_crs(value: str | None) -> str:
    return (value or "").strip().upper()


def _to_dict(value: Any) -> dict[str, object]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _numbers(text: str) -> list[str]:
    import re

    return re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
