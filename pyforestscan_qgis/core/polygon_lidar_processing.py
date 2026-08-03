"""Stable polygon LiDAR processing plan service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .batch_options import BatchExecutionOptions, PolygonBatchOptions
from .direct_lidar_selection import DirectLidarFolderSelector, PolygonLidarSelectionResult, SelectionMethodComparison, compare_selection_methods
from .lidar_inventory import LidarSourceRecord
from .lidar_source_metadata import LidarSourceMetadata
from .polygon_source import NormalizedPolygonSelection
from .polygon_source_selection import PolygonExecutionPlan, PolygonSourceSelectionService, build_polygon_execution_plan
from .types import ProductType


@dataclass(frozen=True)
class PolygonLidarProcessingRequest:
    repository_path: Path
    polygon_selection: NormalizedPolygonSelection
    polygon_crs: str
    repository_crs_override: str | None
    selected_products: tuple[ProductType, ...]
    output_folder: Path
    selection_mode: str = "automatic"
    batch_execution_options: BatchExecutionOptions = BatchExecutionOptions()
    polygon_batch_options: PolygonBatchOptions = PolygonBatchOptions()
    recursive: bool = True
    catalog_path: Path | None = None


@dataclass(frozen=True)
class PolygonLidarProcessingPlan:
    repository_kind: str
    repository_path: Path
    discovered_sources: tuple[LidarSourceMetadata, ...]
    usable_sources: tuple[LidarSourceMetadata, ...]
    selected_sources: tuple[LidarSourceRecord, ...]
    selected_source_paths: tuple[Path, ...]
    rejected_sources: tuple[object, ...]
    polygon_geometry: str
    polygon_crs: str
    comparison_crs: str
    polygon_envelope: object
    selection_method: str
    processing_requests: tuple[dict[str, object], ...]
    masking_plan: dict[str, object]
    output_plan: dict[str, object]
    readiness: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    signature: str
    execution_plan: PolygonExecutionPlan | None = None
    direct_selection: PolygonLidarSelectionResult | None = None
    selection_comparison: SelectionMethodComparison | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "repository_kind": self.repository_kind,
            "repository_path": str(self.repository_path),
            "discovered_sources": [item.to_dict() for item in self.discovered_sources],
            "usable_sources": [item.to_dict() for item in self.usable_sources],
            "selected_source_paths": [str(path) for path in self.selected_source_paths],
            "polygon_geometry": self.polygon_geometry,
            "polygon_crs": self.polygon_crs,
            "comparison_crs": self.comparison_crs,
            "selection_method": self.selection_method,
            "processing_requests": list(self.processing_requests),
            "masking_plan": self.masking_plan,
            "output_plan": self.output_plan,
            "readiness": self.readiness,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "signature": self.signature,
        }

    def debug_summary(self) -> str:
        return "\n".join(
            [
                "Polygon LiDAR Processing Plan",
                f"Repository: {self.repository_path}",
                f"Repository type: {self.repository_kind}",
                f"Files discovered: {len(self.discovered_sources)}",
                f"Metadata usable: {len(self.usable_sources)}",
                f"Effective CRS: {self.comparison_crs}",
                f"Intersecting files: {len(self.selected_source_paths)}",
                f"Selection method: {self.selection_method}",
                f"PBM selected paths: {'available' if self.selected_source_paths else 'none'}",
                f"Exact polygon clipping: {'on' if self.masking_plan.get('exact_raster_mask') else 'off'}",
                f"Readiness: {self.readiness}",
            ]
        )


class PolygonLidarProcessingService:
    """Create a stable plan whose selected paths are the execution contract."""

    def __init__(self, *, source_service: PolygonSourceSelectionService | None = None, direct_selector: DirectLidarFolderSelector | None = None) -> None:
        self.source_service = source_service or PolygonSourceSelectionService()
        self.direct_selector = direct_selector or DirectLidarFolderSelector()

    def create_plan(self, request: PolygonLidarProcessingRequest, *, backend_ready: bool = True, backend_message: str = "PBM backend was not checked.") -> PolygonLidarProcessingPlan:
        repository = self.source_service.resolve_repository(request.repository_path, request.catalog_path)
        blockers: list[str] = []
        warnings: list[str] = list(repository.warnings)
        if not backend_ready:
            blockers.append("Managed processing backend cannot import PyForestScan.")
        if repository.repository_kind == "ept":
            selection = self.source_service.select_sources(repository, request.polygon_selection, catalog_crs=request.repository_crs_override or request.polygon_crs)
            selected_paths = tuple(source.path for source in selection.selected_sources)
            execution = build_polygon_execution_plan(
                repository=repository,
                polygon_context=self.source_service.last_polygon_context,
                source_selection=selection,
                products=tuple(product.value for product in request.selected_products),
                shared_batch_options=request.batch_execution_options,
                polygon_batch_options=request.polygon_batch_options,
                requested_concurrency=request.batch_execution_options.maximum_parallel_jobs,
                effective_concurrency=1,
                output_folder=request.output_folder,
                backend_ready=backend_ready,
                backend_message=backend_message,
            )
            blockers.extend(message.to_text() for message in selection.blockers)
            warnings.extend(message.to_text() for message in selection.warnings)
            return self._plan(request, repository.repository_kind, (), (), selection.selected_sources, selected_paths, selection.rejected_sources, "native_ept", execution, None, None, blockers, warnings)
        direct = self.direct_selector.select(repository.normalized_path, request.polygon_selection, repository_crs_override=request.repository_crs_override or repository.source_crs, recursive=request.recursive)
        selected = direct.selected_sources
        selection_method = "direct_header_metadata"
        comparison = None
        if request.catalog_path is not None and Path(request.catalog_path).exists():
            catalog_selection = self.source_service.select_sources(repository, request.polygon_selection, catalog_crs=request.repository_crs_override or repository.source_crs)
            comparison = compare_selection_methods(direct, catalog_selection.selected_sources, catalog_seconds=0 if catalog_selection.query_result is None else catalog_selection.query_result.query_seconds)
            if request.selection_mode in {"verified_catalog", "catalog"} and not comparison.selected_by_catalog_only and not comparison.selected_by_direct_only and catalog_selection.selected_sources:
                selected = catalog_selection.selected_sources
                selection_method = "verified_catalog"
            elif comparison.selected_by_direct_only or comparison.selected_by_catalog_only:
                warnings.append("Catalog and direct metadata selections differ; beta processing uses direct metadata.")
        blockers.extend(direct.blockers)
        warnings.extend(direct.warnings)
        invariant = selected_path_invariant(selected, ordinary=True)
        blockers.extend(invariant)
        source_selection = self.source_service.select_sources(repository, request.polygon_selection, catalog_crs=request.repository_crs_override or repository.source_crs) if selection_method == "verified_catalog" else None
        if source_selection is not None:
            execution_selection = source_selection
        else:
            from .polygon_batch import _selection_from_direct, _fallback_polygon_context
            from .lidar_catalog_query import derive_polygon_query_geometry

            query_geometry = derive_polygon_query_geometry(request.polygon_selection, catalog_crs=request.repository_crs_override or repository.source_crs or request.polygon_crs)
            execution_selection = _selection_from_direct(repository, _RequestShim(request), query_geometry, direct, self.source_service)
        execution = build_polygon_execution_plan(
            repository=repository,
            polygon_context=self.source_service.last_polygon_context,
            source_selection=execution_selection,
            products=tuple(product.value for product in request.selected_products),
            shared_batch_options=request.batch_execution_options,
            polygon_batch_options=request.polygon_batch_options,
            requested_concurrency=request.batch_execution_options.maximum_parallel_jobs,
            effective_concurrency=1,
            output_folder=request.output_folder,
            backend_ready=backend_ready,
            backend_message=backend_message,
        )
        usable = tuple(item for item in direct.metadata if item.readable and item.effective_crs)
        return self._plan(request, repository.repository_kind, direct.metadata, usable, selected, tuple(source.path for source in selected), direct.rejected_sources, selection_method, execution, direct, comparison, blockers, warnings)

    def _plan(
        self,
        request: PolygonLidarProcessingRequest,
        repository_kind: str,
        discovered: tuple[LidarSourceMetadata, ...],
        usable: tuple[LidarSourceMetadata, ...],
        selected: tuple[LidarSourceRecord, ...],
        selected_paths: tuple[Path, ...],
        rejected: tuple[object, ...],
        selection_method: str,
        execution: PolygonExecutionPlan | None,
        direct: PolygonLidarSelectionResult | None,
        comparison: SelectionMethodComparison | None,
        blockers: list[str],
        warnings: list[str],
    ) -> PolygonLidarProcessingPlan:
        processing_requests = tuple(
            {
                "input_path": str(source.path),
                "source_crs": source.crs or "",
                "crop_polygon": request.polygon_selection.geometry_wkt,
                "products": [product.value for product in request.selected_products],
            }
            for source in selected
        )
        signature = _signature(request, selected_paths, discovered)
        readiness = "ready" if selected_paths and not blockers else "blocked"
        return PolygonLidarProcessingPlan(
            repository_kind=repository_kind,
            repository_path=Path(request.repository_path),
            discovered_sources=discovered,
            usable_sources=usable,
            selected_sources=selected,
            selected_source_paths=selected_paths,
            rejected_sources=rejected,
            polygon_geometry=request.polygon_selection.geometry_wkt,
            polygon_crs=request.polygon_crs,
            comparison_crs=(direct.comparison_crs if direct is not None else request.polygon_crs),
            polygon_envelope=request.polygon_selection.bounds,
            selection_method=selection_method,
            processing_requests=processing_requests,
            masking_plan={"exact_raster_mask": request.polygon_batch_options.exact_raster_mask, "engine": request.polygon_batch_options.mask_engine},
            output_plan={"folder": str(request.output_folder), "registry": "generated_outputs.json"},
            readiness=readiness,
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=tuple(dict.fromkeys(warnings)),
            signature=signature,
            execution_plan=execution,
            direct_selection=direct,
            selection_comparison=comparison,
        )


def selected_path_invariant(sources: tuple[LidarSourceRecord, ...], *, ordinary: bool) -> tuple[str, ...]:
    if not ordinary:
        return ()
    blockers: list[str] = []
    if sources and len(tuple(source.path for source in sources)) != len(sources):
        blockers.append("Selected source path invariant failed: selected path count does not match selected source count.")
    for source in sources:
        path = Path(source.path)
        if not path.exists() or not path.is_file():
            blockers.append(f"Selected source path is not readable: {path}")
    return tuple(blockers)


class _RequestShim:
    def __init__(self, request: PolygonLidarProcessingRequest) -> None:
        self.polygon = request.polygon_selection
        self.output_folder = request.output_folder
        self.products = request.selected_products
        self.settings = None
        self.shared_execution_options = request.batch_execution_options
        self.polygon_options = request.polygon_batch_options


def _signature(request: PolygonLidarProcessingRequest, selected_paths: tuple[Path, ...], metadata: tuple[LidarSourceMetadata, ...]) -> str:
    selected = [str(path.resolve() if path.exists() else path.absolute()) for path in selected_paths]
    signatures = {str(item.path): item.metadata_signature for item in metadata}
    payload = {
        "repository": str(request.repository_path),
        "polygon": request.polygon_selection.geometry_wkt,
        "polygon_crs": request.polygon_crs,
        "products": [product.value for product in request.selected_products],
        "selected_paths": selected,
        "metadata_signatures": signatures,
        "output_folder": str(request.output_folder),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
