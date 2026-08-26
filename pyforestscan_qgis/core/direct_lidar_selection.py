"""Direct polygon-to-LiDAR folder selection.

This is the correctness reference path for ordinary tiled LAS/LAZ/COPC
repositories. It intentionally does not depend on SQLite/RTree catalogs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .lidar_catalog_models import CatalogBuildOptions
from .lidar_inventory import LidarSourceRecord
from .lidar_source_metadata import HeaderMetadataService, LidarSourceMetadata
from .effective_source_spatial_profile import resolve_effective_source_spatial_profile
from .processing_spatial_context import EffectiveSpatialContext, EffectiveSpatialMode, SourceLocalFallbackPolicy
from .polygon_source import NormalizedPolygonSelection
from .spatial_selection import Bounds2D
from .spatial_reference_resolver import SpatialReferenceAssignmentStore


BoundsTransformer = Callable[[Bounds2D, str, str], Bounds2D]


@dataclass(frozen=True)
class DirectRejectedSource:
    path: Path
    reason_code: str
    reason: str
    bounds: Bounds2D | None = None
    embedded_crs: str | None = None
    effective_crs: str | None = None
    metadata_signature: str = ""
    effective_crs_source: str = ""
    raw_overlap: bool | None = None
    spatial_alignment: str = "not_evaluated"


@dataclass(frozen=True)
class PolygonLidarSelectionResult:
    repository_root: Path
    polygon_crs: str
    comparison_crs: str
    polygon_bounds: Bounds2D
    discovered_file_count: int
    metadata_read_count: int
    usable_source_count: int
    intersecting_source_count: int
    intersecting_source_paths: tuple[Path, ...]
    selected_sources: tuple[LidarSourceRecord, ...]
    rejected_sources: tuple[DirectRejectedSource, ...]
    elapsed_seconds: float
    source_of_metadata: str
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: tuple[LidarSourceMetadata, ...] = ()
    selected_metadata: tuple[LidarSourceMetadata, ...] = ()
    spatial_contexts: tuple[EffectiveSpatialContext, ...] = ()


@dataclass(frozen=True)
class SelectionMethodComparison:
    direct: PolygonLidarSelectionResult
    catalog_paths: tuple[Path, ...]
    catalog_seconds: float
    selected_by_direct_only: tuple[Path, ...]
    selected_by_catalog_only: tuple[Path, ...]
    discrepancy_summary: str
    catalog_selection_failure: bool


class DirectLidarFolderSelector:
    """Apply the bbox overlap equation to shared source metadata."""

    def __init__(self, *, metadata_service: HeaderMetadataService | None = None, bounds_transformer: BoundsTransformer | None = None, assignment_store: SpatialReferenceAssignmentStore | None = None, spatial_policy: SourceLocalFallbackPolicy | None = None) -> None:
        self.metadata_service = metadata_service or HeaderMetadataService()
        self.bounds_transformer = bounds_transformer or _default_bounds_transform
        self.assignment_store = assignment_store
        self.spatial_policy = spatial_policy

    def select(
        self,
        repository_root: Path | str,
        polygon: NormalizedPolygonSelection,
        *,
        repository_crs_override: str | None = None,
        recursive: bool = True,
        options: CatalogBuildOptions | None = None,
        metadata: Iterable[LidarSourceMetadata] | None = None,
    ) -> PolygonLidarSelectionResult:
        start = time.perf_counter()
        root = Path(repository_root).expanduser()
        normalized = root.resolve() if root.exists() else root.absolute()
        polygon_crs = (polygon.processing_crs or polygon.source_crs).strip()
        blockers: list[str] = []
        warnings: list[str] = []
        selected: list[LidarSourceRecord] = []
        selected_metadata: list[LidarSourceMetadata] = []
        rejected: list[DirectRejectedSource] = []
        contexts: list[EffectiveSpatialContext] = []
        if not normalized.is_dir():
            return PolygonLidarSelectionResult(normalized, polygon_crs, polygon_crs, polygon.bounds, 0, 0, 0, 0, (), (), (), time.perf_counter() - start, "direct_header_metadata", False, (f"LiDAR repository does not exist: {normalized}",), ())
        records = tuple(metadata) if metadata is not None else self.metadata_service.discover(normalized, repository_crs_override=repository_crs_override, recursive=recursive, options=options)
        if repository_crs_override:
            records = tuple(item.with_repository_crs_override(repository_crs_override) for item in records)
        discovered = len(records)
        metadata_read = sum(1 for item in records if item.readable and item.bounds is not None)
        usable = 0
        comparison_crs_values: set[str] = set()
        for item in records:
            bounds = item.bounds
            if item.source_type not in {"las", "laz", "copc"}:
                continue
            if not item.exists:
                rejected.append(DirectRejectedSource(item.path, "SOURCE_MISSING", "Source file no longer exists.", bounds, item.embedded_crs, item.effective_crs, item.metadata_signature))
                continue
            if not item.readable or bounds is None:
                rejected.append(DirectRejectedSource(item.path, "BOUNDS_MISSING", "; ".join(item.errors) or "Header bounds are unavailable.", bounds, item.embedded_crs, item.effective_crs, item.metadata_signature))
                continue
            profile = resolve_effective_source_spatial_profile(
                item,
                normalized,
                assignment_store=self.assignment_store,
                repository_crs_override=repository_crs_override,
                polygon_crs=polygon_crs,
                polygon_bounds=polygon.bounds,
                policy=self.spatial_policy,
            )
            if profile.context is not None:
                contexts.append(profile.context)
            effective_crs = profile.effective_crs
            raw_overlap = bool(profile.compatibility and profile.compatibility.raw_overlap)
            if profile.conflict:
                rejected.append(DirectRejectedSource(item.path, "CRS_CONFLICT", "Different coordinate systems were detected in this repository.", bounds, item.embedded_crs, None, item.metadata_signature, profile.assignment_source, raw_overlap, "blocked"))
                continue
            if not effective_crs:
                reason = profile.context.blockers[0] if profile.context and profile.context.blockers else "The LiDAR repository does not identify its coordinate system."
                rejected.append(DirectRejectedSource(item.path, "CRS_MISSING", reason, bounds, item.embedded_crs, None, item.metadata_signature, profile.assignment_source, raw_overlap, "blocked"))
                continue
            try:
                query_bounds = _polygon_bounds_for_source(polygon.bounds, polygon_crs, effective_crs, self.bounds_transformer)
            except ValueError as exc:
                rejected.append(DirectRejectedSource(item.path, "CRS_TRANSFORM_UNAVAILABLE", str(exc), bounds, item.embedded_crs, effective_crs, item.metadata_signature, profile.assignment_source, raw_overlap, "blocked"))
                continue
            usable += 1
            comparison_crs_values.add(_norm_crs(effective_crs))
            resolved_item = item.with_repository_crs_override(effective_crs)
            source = resolved_item.to_source_record()
            if _overlaps(bounds, query_bounds):
                selected.append(source)
                selected_metadata.append(resolved_item)
                if profile.mode is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE:
                    warnings.append(f"Using polygon coordinate system {effective_crs} for unreferenced LiDAR; coordinates were not reprojected.")
            else:
                rejected.append(DirectRejectedSource(item.path, "OUTSIDE_QUERY_EXTENT", "Source bounds do not overlap the selected polygon envelope.", bounds, item.embedded_crs, effective_crs, item.metadata_signature, profile.assignment_source, raw_overlap, "verified" if profile.mode is not EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE else "assumed"))
        if discovered == 0:
            blockers.append("No supported LAS, LAZ, or COPC files were found.")
        elif metadata_read == 0:
            blockers.append("LiDAR files were found, but their headers could not be read.")
        elif usable == 0 and any(item.reason_code == "CRS_MISSING" for item in rejected):
            blockers.append("The LiDAR repository does not identify its coordinate system. Use Project CRS or Choose CRS.")
        elif usable == 0 and any(item.reason_code == "CRS_CONFLICT" for item in rejected):
            blockers.append("Different coordinate systems were detected in this repository.")
        elif usable == 0 and any(item.reason_code == "CRS_TRANSFORM_UNAVAILABLE" for item in rejected):
            blockers.append("LiDAR bounds were read, but source and polygon CRSs could not be compared safely.")
        elif not selected:
            blockers.append("The repository is valid, but no LiDAR tiles overlap the selected area.")
        if repository_crs_override:
            warnings.append(f"Repository CRS override applied to CRS-missing files: {repository_crs_override}.")
        comparison_crs = polygon_crs if not comparison_crs_values else (next(iter(comparison_crs_values)) if len(comparison_crs_values) == 1 else "mixed")
        elapsed = time.perf_counter() - start
        return PolygonLidarSelectionResult(
            normalized,
            polygon_crs,
            comparison_crs,
            polygon.bounds,
            discovered,
            metadata_read,
            usable,
            len(selected),
            tuple(source.path for source in selected),
            tuple(selected),
            tuple(rejected),
            elapsed,
            "direct_header_metadata",
            not blockers and bool(selected),
            tuple(dict.fromkeys(blockers)),
            tuple(dict.fromkeys(warnings)),
            records,
            tuple(selected_metadata),
            tuple(contexts),
        )


def compare_selection_methods(direct: PolygonLidarSelectionResult, catalog_sources: tuple[LidarSourceRecord, ...], *, catalog_seconds: float = 0.0) -> SelectionMethodComparison:
    direct_paths = {path.resolve() if path.exists() else path.absolute() for path in direct.intersecting_source_paths}
    catalog_paths = {source.path.resolve() if source.path.exists() else source.path.absolute() for source in catalog_sources}
    direct_only = tuple(sorted(direct_paths - catalog_paths, key=str))
    catalog_only = tuple(sorted(catalog_paths - direct_paths, key=str))
    if direct_only and not catalog_paths:
        summary = "Catalog selection failure: direct metadata found files while catalog selection found none."
    elif direct_only or catalog_only:
        summary = "Catalog and direct metadata selections differ."
    else:
        summary = "Catalog and direct metadata selections match."
    return SelectionMethodComparison(direct, tuple(sorted(catalog_paths, key=str)), catalog_seconds, direct_only, catalog_only, summary, bool(direct_only and not catalog_paths))


def _polygon_bounds_for_source(polygon_bounds: Bounds2D, polygon_crs: str, source_crs: str, transformer: BoundsTransformer | None) -> Bounds2D:
    if _norm_crs(polygon_crs) == _norm_crs(source_crs):
        return polygon_bounds
    if transformer is None:
        raise ValueError("Direct metadata selection cannot compare source and polygon bounds without a CRS transformer.")
    return transformer(polygon_bounds, polygon_crs, source_crs)


def _default_bounds_transform(bounds: Bounds2D, source_crs: str, target_crs: str) -> Bounds2D:
    try:
        from pyproj import Transformer  # type: ignore
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        coordinates = [transformer.transform(x, y) for x, y in ((bounds.xmin, bounds.ymin), (bounds.xmin, bounds.ymax), (bounds.xmax, bounds.ymin), (bounds.xmax, bounds.ymax))]
    except Exception as exc:
        raise ValueError(f"Direct metadata selection cannot transform polygon bounds from {source_crs} to {target_crs}: {exc}") from exc
    xs, ys = zip(*coordinates)
    return Bounds2D(min(xs), min(ys), max(xs), max(ys))


def _overlaps(source: Bounds2D, polygon: Bounds2D) -> bool:
    return source.xmax >= polygon.xmin and source.xmin <= polygon.xmax and source.ymax >= polygon.ymin and source.ymin <= polygon.ymax


def _norm_crs(value: str | None) -> str:
    return (value or "").strip().upper()
