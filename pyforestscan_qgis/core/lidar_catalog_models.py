"""QGIS-free models for persistent LiDAR spatial catalogs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .lidar_inventory import LidarSourceRecord
from .spatial_selection import Bounds2D

CATALOG_SCHEMA_VERSION = 1
DEFAULT_CATALOG_RELATIVE_PATH = Path(".pyforestscan") / "lidar_catalog.sqlite"
DEFAULT_MAX_CANDIDATES = 10_000
DEFAULT_MAX_ESTIMATED_POINTS = 250_000_000
DEFAULT_MAX_ESTIMATED_BYTES = 250 * 1024 * 1024 * 1024
DEFAULT_HEADER_WORKERS = 2
DEFAULT_BATCH_COMMIT_SIZE = 500
DEFAULT_CHECKPOINT_INTERVAL = 5_000


@dataclass(frozen=True)
class CatalogThresholds:
    """Conservative safeguards for large catalog and polygon runs."""

    max_candidates_per_run: int = DEFAULT_MAX_CANDIDATES
    max_estimated_points: int = DEFAULT_MAX_ESTIMATED_POINTS
    max_estimated_input_bytes: int = DEFAULT_MAX_ESTIMATED_BYTES
    max_header_workers: int = DEFAULT_HEADER_WORKERS
    batch_commit_size: int = DEFAULT_BATCH_COMMIT_SIZE
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL


@dataclass(frozen=True)
class LidarCatalogRecord:
    """One persisted LiDAR source record."""

    source_id: str
    source_path: Path
    relative_path: str
    source_type: str
    xmin: float | None = None
    xmax: float | None = None
    ymin: float | None = None
    ymax: float | None = None
    zmin: float | None = None
    zmax: float | None = None
    source_crs: str | None = None
    point_count: int | None = None
    file_size: int = 0
    modified_time_ns: int = 0
    header_signature: str = ""
    inventory_status: str = "indexed"
    metadata_error: str | None = None
    indexed_at: str = ""
    root_id: str = ""

    @property
    def bounds(self) -> Bounds2D | None:
        if self.xmin is None or self.ymin is None or self.xmax is None or self.ymax is None:
            return None
        return Bounds2D(float(self.xmin), float(self.ymin), float(self.xmax), float(self.ymax))

    @property
    def has_bounds(self) -> bool:
        return self.bounds is not None

    def to_source_record(self) -> LidarSourceRecord:
        """Return the existing source record used by Batch execution."""
        return LidarSourceRecord(
            path=self.source_path,
            source_type=self.source_type,
            size_bytes=self.file_size,
            modified_ns=self.modified_time_ns,
            bounds=self.bounds,
            crs=self.source_crs,
            point_count=self.point_count,
        )


@dataclass(frozen=True)
class LidarCatalogSummary:
    """Small catalog status summary for UI and tests."""

    catalog_path: Path
    root_path: Path
    root_id: str
    exists: bool
    source_count: int = 0
    indexed_count: int = 0
    error_count: int = 0
    deleted_count: int = 0
    last_indexed_at: str | None = None
    schema_version: int | None = None


@dataclass(frozen=True)
class LidarCatalogBuildResult:
    """Result from one catalog build/update pass."""

    catalog_path: Path
    root_path: Path
    root_id: str
    discovered_count: int
    indexed_count: int
    unchanged_count: int
    updated_count: int
    error_count: int
    deleted_count: int
    cancelled: bool = False


@dataclass(frozen=True)
class LidarCatalogQuery:
    """Envelope query against a catalog."""

    catalog_path: Path
    root_path: Path
    envelope: Bounds2D
    polygon_wkt: str
    polygon_crs: str
    thresholds: CatalogThresholds = CatalogThresholds()


@dataclass(frozen=True)
class LidarCatalogQueryResult:
    """Catalog query result for polygon Batch preflight."""

    query: LidarCatalogQuery
    records: tuple[LidarCatalogRecord, ...]
    candidate_count: int
    exact_intersecting_count: int
    skipped_count: int
    metadata_error_count: int
    estimated_point_count: int | None
    estimated_bytes: int
    query_seconds: float
    warnings: tuple[str, ...] = ()

    @property
    def source_records(self) -> tuple[LidarSourceRecord, ...]:
        return tuple(record.to_source_record() for record in self.records)


@dataclass(frozen=True)
class PolygonQueryGeometry:
    """Broad query envelope plus exact polygon geometry."""

    envelope: Bounds2D
    exact_polygon_wkt: str
    source_crs: str
    catalog_crs: str
    ept_bounds: tuple[tuple[float, float], tuple[float, float]]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogBuildOptions:
    """Options for streaming catalog construction."""

    recursive: bool = True
    include_globs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    max_depth: int | None = None
    max_source_files: int | None = None
    source_types: tuple[str, ...] = ()
    ignore_hidden: bool = True
    ignore_names: tuple[str, ...] = (".git", "__pycache__", ".pyforestscan", "tmp", "temp", "archive")
    thresholds: CatalogThresholds = CatalogThresholds()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_root_id(root_path: Path | str) -> str:
    """Return a stable root id without hashing file contents."""
    text = str(Path(root_path).expanduser().resolve()).replace("\\", "/").lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def source_id_for(root_id: str, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lower()
    return hashlib.sha256(f"{root_id}:{normalized}".encode("utf-8")).hexdigest()


def default_lidar_catalog_path(root_path: Path | str, workspace_folder: Path | str | None = None) -> Path:
    """Return the preferred catalog location for a LiDAR repository."""
    root = Path(root_path).expanduser()
    preferred = root / DEFAULT_CATALOG_RELATIVE_PATH
    try:
        if root.exists() and root.is_dir():
            marker_parent = preferred.parent
            if marker_parent.exists() or _can_create_directory(marker_parent):
                return preferred
    except OSError:
        pass
    if workspace_folder is None:
        return preferred
    root_id = stable_root_id(root)
    return Path(workspace_folder).expanduser() / ".pyforestscan" / "catalogs" / f"{root_id}.sqlite"


def _can_create_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False
