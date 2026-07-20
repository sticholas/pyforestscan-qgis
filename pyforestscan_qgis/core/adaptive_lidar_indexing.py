"""Adaptive LiDAR repository indexing strategy models and helpers."""

from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .lidar_catalog import catalog_summary, connect_catalog, upsert_records
from .lidar_catalog_builder import inspect_lidar_header
from .lidar_catalog_models import LidarCatalogRecord, default_lidar_catalog_path, source_id_for, stable_root_id, utc_now_iso
from .lidar_catalog_probe import quick_probe_lidar_repository, select_lidar_repository_path
from .lidar_inventory import lidar_source_type
from .spatial_selection import Bounds2D


class LidarIndexStrategy(str, Enum):
    AUTOMATIC = "automatic"
    EXISTING_SPATIAL_INDEX = "existing_spatial_index"
    NATIVE_HIERARCHICAL_SOURCE = "native_hierarchical_source"
    FILENAME_GRID = "filename_grid"
    PARTITIONED_LAZY = "partitioned_lazy"
    FULL_HEADER_CATALOG = "full_header_catalog"


class IndexAccuracy(str, Enum):
    AUTHORITATIVE = "authoritative"
    HIGH = "high"
    VALIDATED_SAMPLE = "validated_sample"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class IndexBuildCost(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class FilenameGridProfile:
    """Approved filename/grid profile for deriving tile bounds without header reads."""

    profile_name: str
    filename_regex: str
    x_group: str
    y_group: str
    tile_width: float
    tile_height: float
    origin_x: float = 0.0
    origin_y: float = 0.0
    crs: str = ""
    coordinate_interpretation: str = "lower_left"
    folder_constraints: tuple[str, ...] = ()
    source_extensions: tuple[str, ...] = (".las", ".laz", ".copc", ".copc.laz")
    approved: bool = False
    validation_tolerance: float = 1.0

    def derive_bounds(self, path: Path | str) -> Bounds2D:
        if not self.approved:
            raise ValueError("Filename/grid profile must be explicitly approved before use.")
        if not self.crs.strip():
            raise ValueError("Filename/grid profile requires a CRS.")
        name = Path(path).name
        match = re.match(self.filename_regex, name)
        if match is None:
            raise ValueError(f"Filename does not match profile {self.profile_name}: {name}")
        try:
            x_value = float(match.group(self.x_group))
            y_value = float(match.group(self.y_group))
        except (IndexError, ValueError) as exc:
            raise ValueError("Filename/grid profile groups could not be read as coordinates.") from exc
        xmin = self.origin_x + x_value
        ymin = self.origin_y + y_value
        return Bounds2D(xmin, ymin, xmin + self.tile_width, ymin + self.tile_height)


@dataclass(frozen=True)
class LidarPartition:
    """One partition in a partitioned lazy index."""

    partition_id: str
    relative_path: str
    bounds: Bounds2D
    crs: str
    source_count_estimate: int | None = None
    index_status: str = "not_indexed"
    modified_signature: str = ""
    child_catalog_path: Path | None = None
    indexing_error: str | None = None


@dataclass(frozen=True)
class RepositoryCapabilities:
    """Bounded capability detection result."""

    root_path: Path
    existing_plugin_catalog: Path | None = None
    existing_pdal_tindex: Path | None = None
    existing_vector_footprint_index: Path | None = None
    ept_roots: tuple[Path, ...] = ()
    copc_sources: tuple[Path, ...] = ()
    filename_grid_profile: FilenameGridProfile | None = None
    partition_profile: tuple[LidarPartition, ...] = ()
    generic_las_laz_sources: tuple[Path, ...] = ()
    estimated_repository_scale: str = "unknown"
    detection_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepositoryIndexPlan:
    """Selected indexing strategy and expected cost."""

    selected_strategy: LidarIndexStrategy
    reason: str
    sources_to_register: tuple[Path, ...] = ()
    partitions_to_index: tuple[LidarPartition, ...] = ()
    files_requiring_header_inspection: int | None = None
    files_avoided: int | None = None
    expected_accuracy: IndexAccuracy = IndexAccuracy.UNKNOWN
    expected_build_cost: IndexBuildCost = IndexBuildCost.MODERATE
    warnings: tuple[str, ...] = ()
    requires_user_confirmation: bool = False


@dataclass(frozen=True)
class ExistingIndexFieldMapping:
    """Field mapping for an existing footprint index."""

    source_path: str = "source_path"
    xmin: str = "xmin"
    xmax: str = "xmax"
    ymin: str = "ymin"
    ymax: str = "ymax"
    crs: str | None = "crs"
    point_count: str | None = "point_count"
    source_type: str | None = "source_type"


@dataclass(frozen=True)
class TwoPassCatalogPlan:
    """Full catalog fallback split into spatial and metadata enrichment passes."""

    pass1_state: str = "spatial_ready"
    pass1_fields: tuple[str, ...] = ("source_path", "source_type", "file_size", "modified_time", "xmin", "xmax", "ymin", "ymax", "minimal_crs")
    pass2_state: str = "deferred_enrichment"
    pass2_fields: tuple[str, ...] = ("full_crs_wkt", "point_count", "z_bounds", "point_format", "classifications", "dimensions")
    polygon_queries_allowed_after_pass1: bool = True


@dataclass(frozen=True)
class CatalogPerformanceReport:
    """Performance report for catalog diagnostics."""

    selected_strategy: LidarIndexStrategy
    repository_type: str
    storage_type: str
    files_discovered: int = 0
    files_header_inspected: int = 0
    files_avoided: int = 0
    directories_traversed: int = 0
    traversal_rate: float | None = None
    header_rate: float | None = None
    sqlite_write_rate: float | None = None
    elapsed_by_stage: dict[str, float] | None = None
    worker_count: int = 1
    metadata_errors: int = 0
    catalog_size_bytes: int = 0
    query_seconds: float | None = None

    @property
    def dominant_bottleneck(self) -> str:
        rates = {
            "traversal": self.traversal_rate,
            "header decoding": self.header_rate,
            "SQLite write": self.sqlite_write_rate,
        }
        known = {key: value for key, value in rates.items() if value is not None and value > 0}
        if not known:
            return "unknown"
        return min(known, key=known.get)


def detect_repository_capabilities(
    root_path: Path | str,
    *,
    existing_index_path: Path | str | None = None,
    filename_profile: FilenameGridProfile | None = None,
    partitions: tuple[LidarPartition, ...] = (),
    max_entries: int = 500,
    max_seconds: float = 2.0,
) -> RepositoryCapabilities:
    """Bounded detection of trustworthy indexing strategies."""
    selection = select_lidar_repository_path(root_path)
    root = selection.normalized_path
    warnings: list[str] = []
    if not selection.valid:
        warnings.append(selection.message)
    probe = quick_probe_lidar_repository(root, max_entries=max_entries, max_seconds=max_seconds) if selection.valid else None
    existing_catalog = selection.catalog_path if selection.catalog_exists else None
    vector_index = Path(existing_index_path).expanduser() if existing_index_path else _find_top_level_existing_index(root, max_entries=max_entries, max_seconds=max_seconds)
    pdal_tindex = vector_index if vector_index and _looks_like_pdal_tindex(vector_index) else None
    ept_roots: list[Path] = []
    copc_sources: list[Path] = []
    generic: list[Path] = []
    if selection.valid:
        start = time.monotonic()
        try:
            for index, child in enumerate(root.iterdir()):
                if index >= max_entries or time.monotonic() - start >= max_seconds:
                    warnings.append("Capability detection stopped at bounded top-level sample; deeply nested indexes may still exist.")
                    break
                ept_metadata = child / "ept.json" if child.is_dir() else None
                source_candidate = ept_metadata if ept_metadata is not None and ept_metadata.exists() else child
                source_type = lidar_source_type(source_candidate, include_ept=True)
                if source_type == "ept":
                    ept_roots.append(source_candidate)
                elif source_type == "copc":
                    copc_sources.append(child)
                elif source_type in {"las", "laz"}:
                    generic.append(child)
        except OSError as exc:
            warnings.append(f"Top-level capability probe failed: {exc}")
    scale = "unknown"
    if probe is not None and probe.stopped_by_limit:
        scale = "large_or_unknown"
    elif probe is not None and probe.inspected_entries < 50:
        scale = "small_sample"
    return RepositoryCapabilities(
        root_path=root,
        existing_plugin_catalog=existing_catalog,
        existing_pdal_tindex=pdal_tindex,
        existing_vector_footprint_index=vector_index if vector_index != pdal_tindex else None,
        ept_roots=tuple(ept_roots),
        copc_sources=tuple(copc_sources),
        filename_grid_profile=filename_profile,
        partition_profile=partitions,
        generic_las_laz_sources=tuple(generic),
        estimated_repository_scale=scale,
        detection_warnings=tuple(dict.fromkeys(warnings)),
    )


def choose_index_strategy(capabilities: RepositoryCapabilities, *, polygon_bounds: Bounds2D | None = None, requested: LidarIndexStrategy = LidarIndexStrategy.AUTOMATIC) -> RepositoryIndexPlan:
    """Choose the safest available indexing strategy."""
    if requested is not LidarIndexStrategy.AUTOMATIC:
        return _plan_for_requested(capabilities, requested, polygon_bounds=polygon_bounds)
    if capabilities.existing_plugin_catalog:
        return RepositoryIndexPlan(
            LidarIndexStrategy.EXISTING_SPATIAL_INDEX,
            "Existing PyForestScan SQLite catalog is available and can be queried immediately.",
            sources_to_register=(capabilities.existing_plugin_catalog,),
            files_requiring_header_inspection=0,
            files_avoided=None,
            expected_accuracy=IndexAccuracy.HIGH,
            expected_build_cost=IndexBuildCost.NONE,
            warnings=capabilities.detection_warnings,
        )
    if capabilities.existing_pdal_tindex or capabilities.existing_vector_footprint_index:
        index = capabilities.existing_pdal_tindex or capabilities.existing_vector_footprint_index
        return RepositoryIndexPlan(
            LidarIndexStrategy.EXISTING_SPATIAL_INDEX,
            "Existing footprint/tile index can be registered without rereading every source header.",
            sources_to_register=(index,) if index else (),
            files_requiring_header_inspection=0,
            expected_accuracy=IndexAccuracy.VALIDATED_SAMPLE,
            expected_build_cost=IndexBuildCost.LOW,
            warnings=capabilities.detection_warnings,
            requires_user_confirmation=True,
        )
    native_sources = (*capabilities.ept_roots, *capabilities.copc_sources)
    if native_sources and not capabilities.generic_las_laz_sources:
        return RepositoryIndexPlan(
            LidarIndexStrategy.NATIVE_HIERARCHICAL_SOURCE,
            "Repository sample is dominated by EPT/COPC sources that are spatially queryable as logical sources.",
            sources_to_register=tuple(native_sources),
            files_requiring_header_inspection=len(capabilities.copc_sources),
            files_avoided=None,
            expected_accuracy=IndexAccuracy.HIGH,
            expected_build_cost=IndexBuildCost.LOW,
            warnings=capabilities.detection_warnings,
        )
    if capabilities.filename_grid_profile and capabilities.filename_grid_profile.approved:
        return RepositoryIndexPlan(
            LidarIndexStrategy.FILENAME_GRID,
            "Approved filename/grid profile can derive source footprints without opening every header.",
            files_requiring_header_inspection=0,
            expected_accuracy=IndexAccuracy.VALIDATED_SAMPLE,
            expected_build_cost=IndexBuildCost.LOW,
            warnings=capabilities.detection_warnings,
            requires_user_confirmation=True,
        )
    if capabilities.partition_profile:
        partitions = tuple(_filter_partitions(capabilities.partition_profile, polygon_bounds)) if polygon_bounds else capabilities.partition_profile
        avoided = None if polygon_bounds is None else max(0, len(capabilities.partition_profile) - len(partitions))
        return RepositoryIndexPlan(
            LidarIndexStrategy.PARTITIONED_LAZY,
            "Mapped repository partitions allow indexing only polygon-relevant partitions first.",
            partitions_to_index=partitions,
            files_requiring_header_inspection=sum((item.source_count_estimate or 0) for item in partitions) or None,
            files_avoided=avoided,
            expected_accuracy=IndexAccuracy.HIGH,
            expected_build_cost=IndexBuildCost.MODERATE,
            warnings=capabilities.detection_warnings,
        )
    return RepositoryIndexPlan(
        LidarIndexStrategy.FULL_HEADER_CATALOG,
        "No trustworthy existing, native, filename, or partition index was detected in the bounded probe; use spatial-first full header catalog fallback.",
        files_requiring_header_inspection=None,
        expected_accuracy=IndexAccuracy.HIGH,
        expected_build_cost=IndexBuildCost.VERY_HIGH if capabilities.estimated_repository_scale == "large_or_unknown" else IndexBuildCost.HIGH,
        warnings=capabilities.detection_warnings,
        requires_user_confirmation=capabilities.estimated_repository_scale == "large_or_unknown",
    )


def format_repository_index_plan(plan: RepositoryIndexPlan) -> str:
    lines = [
        f"Strategy: {plan.selected_strategy.value}",
        f"Reason: {plan.reason}",
        f"Expected accuracy: {plan.expected_accuracy.value}",
        f"Expected build cost: {plan.expected_build_cost.value}",
        f"Files requiring header inspection: {_count_text(plan.files_requiring_header_inspection)}",
        f"Files avoided: {_count_text(plan.files_avoided)}",
    ]
    if plan.partitions_to_index:
        lines.append(f"Partitions to index: {len(plan.partitions_to_index)}")
    if plan.sources_to_register:
        lines.append("Sources/indexes to register:")
        lines.extend(f"- {path}" for path in plan.sources_to_register[:20])
    if plan.requires_user_confirmation:
        lines.append("Confirmation required before using this strategy.")
    if plan.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in plan.warnings)
    return "\n".join(lines)


def read_existing_footprint_index(index_path: Path | str, root_path: Path | str, *, mapping: ExistingIndexFieldMapping = ExistingIndexFieldMapping()) -> tuple[LidarCatalogRecord, ...]:
    """Read a simple existing footprint index without inspecting every source."""
    path = Path(index_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        rows = _read_csv_rows(path)
    elif suffix in {".geojson", ".json"}:
        rows = _read_geojson_rows(path, mapping)
    elif suffix in {".gpkg", ".shp", ".fgb"}:
        raise ValueError("GeoPackage/Shapefile/FlatGeobuf registration requires QGIS/OGR field mapping in the UI layer.")
    else:
        raise ValueError(f"Unsupported footprint index format: {suffix}")
    root = Path(root_path).expanduser().resolve()
    root_id = stable_root_id(root)
    records: list[LidarCatalogRecord] = []
    for row in rows:
        source = Path(str(row[mapping.source_path]))
        if not source.is_absolute():
            source = root / source
        source_type = str(row.get(mapping.source_type or "", "") or lidar_source_type(source, include_ept=True) or source.suffix.lstrip(".") or "unknown")
        relative = source.relative_to(root).as_posix() if _is_relative_to(source, root) else source.name
        records.append(
            LidarCatalogRecord(
                source_id=source_id_for(root_id, relative),
                source_path=source,
                relative_path=relative,
                source_type=source_type,
                xmin=float(row[mapping.xmin]),
                xmax=float(row[mapping.xmax]),
                ymin=float(row[mapping.ymin]),
                ymax=float(row[mapping.ymax]),
                source_crs=str(row.get(mapping.crs or "", "") or "") or None,
                point_count=_optional_int(row.get(mapping.point_count or "")),
                file_size=source.stat().st_size if source.exists() else 0,
                modified_time_ns=source.stat().st_mtime_ns if source.exists() else 0,
                header_signature="existing-index",
                inventory_status="indexed" if source.exists() else "error",
                metadata_error=None if source.exists() else "Source path from existing index does not exist.",
                indexed_at=utc_now_iso(),
                root_id=root_id,
            )
        )
    return tuple(records)


def register_existing_footprint_index(index_path: Path | str, root_path: Path | str, catalog_path: Path | str | None = None, *, mapping: ExistingIndexFieldMapping = ExistingIndexFieldMapping()) -> Path:
    """Import an existing index into the plugin SQLite catalog without rereading source headers."""
    root = Path(root_path).expanduser().resolve()
    catalog = Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(root)
    records = read_existing_footprint_index(index_path, root, mapping=mapping)
    connection = connect_catalog(catalog)
    try:
        upsert_records(connection, records)
        connection.commit()
    finally:
        connection.close()
    return catalog


def register_native_sources(root_path: Path | str, sources: Iterable[Path], catalog_path: Path | str | None = None) -> Path:
    """Register EPT/COPC as logical spatial sources without inspecting internal nodes/chunks."""
    root = Path(root_path).expanduser().resolve()
    catalog = Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(root)
    root_id = stable_root_id(root)
    records = [inspect_lidar_header(Path(source), root, root_id) for source in sources]
    connection = connect_catalog(catalog)
    try:
        upsert_records(connection, records)
        connection.commit()
    finally:
        connection.close()
    return catalog


def records_from_filename_grid(root_path: Path | str, paths: Iterable[Path], profile: FilenameGridProfile) -> tuple[LidarCatalogRecord, ...]:
    """Create catalog records from an approved filename/grid profile."""
    root = Path(root_path).expanduser().resolve()
    root_id = stable_root_id(root)
    records: list[LidarCatalogRecord] = []
    for path in paths:
        bounds = profile.derive_bounds(path)
        source = Path(path)
        relative = source.relative_to(root).as_posix() if _is_relative_to(source, root) else source.name
        stat = source.stat() if source.exists() else None
        records.append(
            LidarCatalogRecord(
                source_id=source_id_for(root_id, relative),
                source_path=source,
                relative_path=relative,
                source_type=lidar_source_type(source, include_ept=True) or source.suffix.lstrip("."),
                xmin=bounds.xmin,
                xmax=bounds.xmax,
                ymin=bounds.ymin,
                ymax=bounds.ymax,
                source_crs=profile.crs,
                file_size=0 if stat is None else stat.st_size,
                modified_time_ns=0 if stat is None else stat.st_mtime_ns,
                header_signature=f"filename-grid:{profile.profile_name}",
                indexed_at=utc_now_iso(),
                root_id=root_id,
            )
        )
    return tuple(records)


def select_partitions_for_polygon(partitions: Iterable[LidarPartition], polygon_bounds: Bounds2D) -> tuple[LidarPartition, ...]:
    return tuple(_filter_partitions(tuple(partitions), polygon_bounds))


def current_polygon_coverage(selected_partitions: tuple[LidarPartition, ...]) -> float:
    if not selected_partitions:
        return 0.0
    ready = sum(1 for item in selected_partitions if item.index_status in {"indexed", "spatial_ready", "ready"})
    return round((ready / len(selected_partitions)) * 100.0, 2)


def two_pass_full_catalog_plan() -> TwoPassCatalogPlan:
    return TwoPassCatalogPlan()


def audit_persistent_worker_lifecycle(files_processed: int, subprocess_launches: int) -> tuple[bool, str]:
    """Return whether catalog inspection avoids per-file subprocess startup."""
    if files_processed <= 1:
        return True, "Not enough files to assess process reuse."
    if subprocess_launches > 1 and subprocess_launches >= files_processed:
        return False, "Catalog inspection appears to launch one process per file."
    return True, "Catalog inspection uses a persistent job/worker lifecycle rather than one subprocess per file."


def _plan_for_requested(capabilities: RepositoryCapabilities, requested: LidarIndexStrategy, *, polygon_bounds: Bounds2D | None) -> RepositoryIndexPlan:
    if requested is LidarIndexStrategy.EXISTING_SPATIAL_INDEX:
        index = capabilities.existing_plugin_catalog or capabilities.existing_pdal_tindex or capabilities.existing_vector_footprint_index
        return RepositoryIndexPlan(requested, "User selected an existing spatial index strategy.", sources_to_register=(index,) if index else (), expected_accuracy=IndexAccuracy.VALIDATED_SAMPLE, expected_build_cost=IndexBuildCost.LOW, requires_user_confirmation=True, warnings=capabilities.detection_warnings)
    if requested is LidarIndexStrategy.NATIVE_HIERARCHICAL_SOURCE:
        return RepositoryIndexPlan(requested, "User selected EPT/COPC native registration.", sources_to_register=(*capabilities.ept_roots, *capabilities.copc_sources), files_requiring_header_inspection=len(capabilities.copc_sources), expected_accuracy=IndexAccuracy.HIGH, expected_build_cost=IndexBuildCost.LOW, warnings=capabilities.detection_warnings)
    if requested is LidarIndexStrategy.FILENAME_GRID:
        return RepositoryIndexPlan(requested, "User selected filename/grid profile indexing.", files_requiring_header_inspection=0, expected_accuracy=IndexAccuracy.VALIDATED_SAMPLE, expected_build_cost=IndexBuildCost.LOW, requires_user_confirmation=True, warnings=capabilities.detection_warnings)
    if requested is LidarIndexStrategy.PARTITIONED_LAZY:
        partitions = tuple(_filter_partitions(capabilities.partition_profile, polygon_bounds)) if polygon_bounds else capabilities.partition_profile
        avoided = None if polygon_bounds is None else max(0, len(capabilities.partition_profile) - len(partitions))
        return RepositoryIndexPlan(requested, "User selected partitioned lazy indexing.", partitions_to_index=partitions, files_requiring_header_inspection=sum((item.source_count_estimate or 0) for item in partitions) or None, files_avoided=avoided, expected_accuracy=IndexAccuracy.HIGH, expected_build_cost=IndexBuildCost.MODERATE, warnings=capabilities.detection_warnings)
    return RepositoryIndexPlan(LidarIndexStrategy.FULL_HEADER_CATALOG, "User selected spatial-first full header catalog fallback.", expected_accuracy=IndexAccuracy.HIGH, expected_build_cost=IndexBuildCost.HIGH, requires_user_confirmation=True, warnings=capabilities.detection_warnings)


def _filter_partitions(partitions: Iterable[LidarPartition], polygon_bounds: Bounds2D | None) -> tuple[LidarPartition, ...]:
    if polygon_bounds is None:
        return tuple(partitions)
    return tuple(item for item in partitions if item.bounds.intersects(polygon_bounds))


def _find_top_level_existing_index(root: Path, *, max_entries: int, max_seconds: float) -> Path | None:
    if not root.is_dir():
        return None
    start = time.monotonic()
    try:
        for index, child in enumerate(root.iterdir()):
            if index >= max_entries or time.monotonic() - start >= max_seconds:
                break
            if child.suffix.lower() in {".gpkg", ".shp", ".geojson", ".json", ".fgb", ".csv"} and any(token in child.stem.lower() for token in ("tile", "tindex", "footprint", "index")):
                return child
    except OSError:
        return None
    return None


def _looks_like_pdal_tindex(path: Path) -> bool:
    return any(token in path.stem.lower() for token in ("tindex", "tileindex", "tile_index"))


def _read_csv_rows(path: Path) -> tuple[dict[str, object], ...]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _read_geojson_rows(path: Path, mapping: ExistingIndexFieldMapping) -> tuple[dict[str, object], ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, dict) else []
    rows: list[dict[str, object]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = dict(feature.get("properties", {}) or {})
        bbox = feature.get("bbox") or props.get("bbox")
        if bbox is None:
            bbox = _geometry_bbox(feature.get("geometry"))
        if isinstance(bbox, list) and len(bbox) >= 4:
            props.setdefault(mapping.xmin, bbox[0])
            props.setdefault(mapping.ymin, bbox[1])
            props.setdefault(mapping.xmax, bbox[2])
            props.setdefault(mapping.ymax, bbox[3])
        rows.append(props)
    return tuple(rows)


def _geometry_bbox(geometry: object) -> list[float] | None:
    if not isinstance(geometry, dict):
        return None
    coords: list[float] = []
    def walk(value):
        if isinstance(value, list):
            if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                coords.extend([float(value[0]), float(value[1])])
            else:
                for item in value:
                    walk(item)
    walk(geometry.get("coordinates"))
    if len(coords) < 2:
        return None
    xs = coords[0::2]
    ys = coords[1::2]
    return [min(xs), min(ys), max(xs), max(ys)]


def _optional_int(value: object) -> int | None:
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def _count_text(value: int | None) -> str:
    return "unknown" if value is None else f"{value:,}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
