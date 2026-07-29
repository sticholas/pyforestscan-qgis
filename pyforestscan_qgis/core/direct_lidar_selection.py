"""Direct polygon-to-LiDAR folder selection.

This is the correctness reference path for ordinary tiled LAS/LAZ/COPC
repositories. It intentionally does not depend on SQLite/RTree catalogs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .lidar_catalog_builder import inspect_lidar_header, iter_lidar_paths
from .lidar_catalog_models import CatalogBuildOptions, LidarCatalogRecord, stable_root_id
from .lidar_inventory import LidarSourceRecord
from .polygon_source import NormalizedPolygonSelection
from .spatial_selection import Bounds2D


HeaderReader = Callable[[Path, Path, str], LidarCatalogRecord]


@dataclass(frozen=True)
class DirectRejectedSource:
    path: Path
    reason_code: str
    reason: str
    bounds: Bounds2D | None = None
    embedded_crs: str | None = None
    effective_crs: str | None = None


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
    """Discover headers and apply the bbox overlap equation directly."""

    def __init__(self, *, header_reader: HeaderReader | None = None) -> None:
        self.header_reader = header_reader or inspect_lidar_header

    def select(
        self,
        repository_root: Path | str,
        polygon: NormalizedPolygonSelection,
        *,
        repository_crs_override: str | None = None,
        recursive: bool = True,
        options: CatalogBuildOptions | None = None,
    ) -> PolygonLidarSelectionResult:
        start = time.perf_counter()
        root = Path(repository_root).expanduser()
        normalized = root.resolve() if root.exists() else root.absolute()
        polygon_crs = (polygon.processing_crs or polygon.source_crs).strip()
        comparison_crs = (repository_crs_override or polygon_crs).strip()
        blockers: list[str] = []
        warnings: list[str] = []
        selected: list[LidarSourceRecord] = []
        rejected: list[DirectRejectedSource] = []
        metadata_read = 0
        discovered = 0
        usable = 0
        if not normalized.is_dir():
            return PolygonLidarSelectionResult(normalized, polygon_crs, comparison_crs, polygon.bounds, 0, 0, 0, 0, (), (), (), time.perf_counter() - start, "direct_header_scan", False, (f"LiDAR repository does not exist: {normalized}",), ())
        scan_options = options or CatalogBuildOptions(recursive=recursive, source_types=("las", "laz", "copc"))
        if options is None and not recursive:
            scan_options = CatalogBuildOptions(recursive=False, source_types=("las", "laz", "copc"))
        root_id = stable_root_id(normalized)
        for path in iter_lidar_paths(normalized, options=scan_options):
            source_type = path.suffix.lower().lstrip(".")
            if str(path).lower().endswith(".copc.laz"):
                source_type = "copc"
            if source_type not in {"las", "laz", "copc"}:
                continue
            discovered += 1
            try:
                record = self.header_reader(path, normalized, root_id)
                metadata_read += 1
            except Exception as exc:  # noqa: BLE001 - selection must surface per-file failures.
                rejected.append(DirectRejectedSource(path, "HEADER_READ_FAILED", str(exc)))
                continue
            if record.bounds is None:
                rejected.append(DirectRejectedSource(path, "BOUNDS_MISSING", "Header bounds are unavailable.", embedded_crs=record.source_crs))
                continue
            effective_crs = record.source_crs or repository_crs_override
            if not effective_crs:
                rejected.append(DirectRejectedSource(path, "CRS_MISSING", "LiDAR bounds were read, but their coordinate system is unknown.", record.bounds, record.source_crs, None))
                continue
            if _norm_crs(effective_crs) != _norm_crs(polygon_crs):
                rejected.append(DirectRejectedSource(path, "CRS_TRANSFORM_UNAVAILABLE", "Direct scan cannot compare source and polygon bounds without a CRS transformer.", record.bounds, record.source_crs, effective_crs))
                continue
            usable += 1
            source = LidarSourceRecord(path, record.source_type, record.file_size, record.modified_time_ns, bounds=record.bounds, crs=effective_crs, point_count=record.point_count)
            if _overlaps(record.bounds, polygon.bounds):
                selected.append(source)
            else:
                rejected.append(DirectRejectedSource(path, "OUTSIDE_QUERY_EXTENT", "Source bounds do not overlap the selected polygon bounds.", record.bounds, record.source_crs, effective_crs))
        if discovered == 0:
            blockers.append("No supported LAS, LAZ, or COPC files were found.")
        elif metadata_read == 0:
            blockers.append("LiDAR files were found, but their headers could not be read.")
        elif usable == 0 and any(item.reason_code == "CRS_MISSING" for item in rejected):
            blockers.append("LiDAR bounds were read, but their coordinate system is unknown.")
        elif not selected:
            blockers.append("The repository is valid, but no LiDAR tiles overlap the selected area.")
        if repository_crs_override:
            warnings.append(f"Repository CRS override applied to CRS-missing files: {repository_crs_override}.")
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
            "direct_header_scan",
            not blockers and bool(selected),
            tuple(dict.fromkeys(blockers)),
            tuple(dict.fromkeys(warnings)),
        )


def compare_selection_methods(direct: PolygonLidarSelectionResult, catalog_sources: tuple[LidarSourceRecord, ...], *, catalog_seconds: float = 0.0) -> SelectionMethodComparison:
    direct_paths = {path.resolve() if path.exists() else path.absolute() for path in direct.intersecting_source_paths}
    catalog_paths = {source.path.resolve() if source.path.exists() else source.path.absolute() for source in catalog_sources}
    direct_only = tuple(sorted(direct_paths - catalog_paths, key=str))
    catalog_only = tuple(sorted(catalog_paths - direct_paths, key=str))
    if direct_only and not catalog_paths:
        summary = "Catalog selection failure: direct scan found files while catalog selection found none."
    elif direct_only or catalog_only:
        summary = "Catalog and direct selections differ."
    else:
        summary = "Catalog and direct selections match."
    return SelectionMethodComparison(direct, tuple(sorted(catalog_paths, key=str)), catalog_seconds, direct_only, catalog_only, summary, bool(direct_only and not catalog_paths))


def _overlaps(source: Bounds2D, polygon: Bounds2D) -> bool:
    return source.xmax >= polygon.xmin and source.xmin <= polygon.xmax and source.ymax >= polygon.ymin and source.ymin <= polygon.ymax


def _norm_crs(value: str | None) -> str:
    return (value or "").strip().upper()
