"""Catalog identity, integrity, repair, and source-view helpers."""

from __future__ import annotations

import json
import math
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .lidar_catalog import connect_catalog
from .lidar_catalog_models import CATALOG_SCHEMA_VERSION, stable_root_id, utc_now_iso
from .spatial_selection import Bounds2D

SKIP_HEADER_READ_FAILED = "HEADER_READ_FAILED"
SKIP_CRS_MISSING = "CRS_MISSING"
SKIP_BOUNDS_MISSING = "BOUNDS_MISSING"
SKIP_BOUNDS_INVALID = "BOUNDS_INVALID"
SKIP_BOUNDS_NONFINITE = "BOUNDS_NONFINITE"
SKIP_FILE_MISSING = "FILE_MISSING"
SKIP_FILE_CHANGED = "FILE_CHANGED"
SKIP_STALE_RECORD = "STALE_RECORD"
SKIP_RTREE_ENTRY_MISSING = "RTREE_ENTRY_MISSING"
SKIP_RTREE_ENTRY_INVALID = "RTREE_ENTRY_INVALID"


@dataclass(frozen=True)
class CatalogIdentity:
    schema_version: int | None
    repository_root: Path
    normalized_repository_root: Path
    repository_fingerprint: str
    creation_time: str | None = None
    last_update_time: str | None = None
    plugin_version: str = "unknown"
    header_reader_version: str = "las-public-header-v1"
    source_count: int = 0
    usable_spatial_source_count: int = 0
    rtree_row_count: int = 0
    failed_metadata_count: int = 0
    repository_crs_override: str | None = None
    crs_override_source: str | None = None


@dataclass(frozen=True)
class RepositoryCrsOverride:
    crs: str
    assigned_at: str
    assigned_by: str
    method: str
    note: str = ""


@dataclass(frozen=True)
class ExtentDefiningSource:
    role: str
    source_path: Path
    value: float
    source_id: str


@dataclass(frozen=True)
class CatalogRecordInspectionReport:
    catalog_path: Path
    catalog_repository_root: Path
    selected_repository_root: Path
    repository_fingerprint: str
    source_row_count: int
    rtree_row_count: int
    first_paths: tuple[Path, ...]
    last_paths: tuple[Path, ...]
    sample_paths: tuple[Path, ...]
    extent_defining_sources: tuple[ExtentDefiningSource, ...]
    catalog_created_at: str | None
    catalog_updated_at: str | None


@dataclass(frozen=True)
class CatalogIntegrityReport:
    catalog_path: Path
    repository_root: Path
    root_id: str
    status: str
    sqlite_opens: bool
    schema_valid: bool
    metadata_valid: bool
    repository_root_matches: bool
    source_row_count: int = 0
    enabled_source_row_count: int = 0
    valid_bounds_row_count: int = 0
    rtree_row_count: int = 0
    source_rows_missing_rtree_entries: int = 0
    rtree_rows_missing_source_records: int = 0
    duplicate_source_paths: int = 0
    duplicate_source_ids: int = 0
    malformed_extents: int = 0
    stale_files: int = 0
    missing_files: int = 0
    crs_distribution: dict[str, int] = field(default_factory=dict)
    extent_union: Bounds2D | None = None
    skip_reason_counts: dict[str, int] = field(default_factory=dict)
    messages: tuple[str, ...] = ()
    identity: CatalogIdentity | None = None
    embedded_crs_known_count: int = 0
    crs_unknown_bounded_count: int = 0
    effective_crs_known_count: int = 0
    effective_crs_unknown_count: int = 0
    repository_crs_override: str | None = None

    @property
    def spatially_usable(self) -> bool:
        return self.status in {"Healthy", "Healthy with validated repository CRS override"} and self.usable_spatial_source_count > 0

    @property
    def usable_spatial_source_count(self) -> int:
        return self.rtree_row_count

    def preflight_blocker_message(self) -> str | None:
        if self.status in {"Healthy", "Healthy with validated repository CRS override"}:
            return None
        if self.status == "CRS Assignment Required":
            return "LiDAR files were indexed, but their coordinate system is unknown. Coverage cannot yet be compared with the selected polygon."
        if self.status == "Empty":
            return "No supported LAS, LAZ, COPC, or EPT data was found in this folder." if self.source_row_count == 0 else "Repository catalog is empty."
        if self.source_row_count and self.rtree_row_count == 0:
            return "LiDAR files were found, but their spatial bounds are unavailable."
        if self.source_rows_missing_rtree_entries or self.rtree_rows_missing_source_records:
            return "The repository catalog is incomplete and must be repaired."
        if self.missing_files:
            return "The repository catalog references files that are missing; refresh or repair the catalog."
        return "Repository catalog is not spatially usable."

    def summary_lines(self) -> tuple[str, ...]:
        extent = "Unavailable"
        if self.extent_union is not None:
            extent = f"X {self.extent_union.xmin:g}-{self.extent_union.xmax:g}; Y {self.extent_union.ymin:g}-{self.extent_union.ymax:g}"
        return (
            f"Catalog status: {self.status}",
            f"Sources: {self.source_row_count:,}; spatial records: {self.rtree_row_count:,}; metadata errors: {self.failed_metadata_count:,}",
            f"Embedded CRS known: {self.embedded_crs_known_count:,}; CRS-unknown bounded sources: {self.crs_unknown_bounded_count:,}",
            f"Effective CRS-known sources: {self.effective_crs_known_count:,}; override: {self.repository_crs_override or 'none'}",
            f"Missing RTree entries: {self.source_rows_missing_rtree_entries:,}; orphan RTree rows: {self.rtree_rows_missing_source_records:,}",
            f"Coverage extent: {extent}",
        )

    @property
    def failed_metadata_count(self) -> int:
        return int(self.skip_reason_counts.get(SKIP_HEADER_READ_FAILED, 0))


@dataclass(frozen=True)
class CatalogRepairReport:
    catalog_path: Path
    backup_path: Path | None
    before: CatalogIntegrityReport
    after: CatalogIntegrityReport
    operations: tuple[str, ...]
    repaired: bool
    message: str


@dataclass(frozen=True)
class RepositorySourceViewRow:
    file: str
    source_type: str
    status: str
    crs: str
    embedded_crs: str
    effective_crs: str
    crs_source: str
    xmin: float | None
    xmax: float | None
    ymin: float | None
    ymax: float | None
    points: int | None
    modified_time_ns: int
    problem: str
    has_rtree: bool


def write_catalog_identity(connection: sqlite3.Connection, root_path: Path | str, *, source_count: int | None = None) -> None:
    root = Path(root_path).expanduser()
    root_id = stable_root_id(root)
    row = connection.execute(
        "SELECT COUNT(*) AS sources, SUM(CASE WHEN inventory_status='error' THEN 1 ELSE 0 END) AS errors FROM lidar_sources WHERE root_id=?",
        (root_id,),
    ).fetchone()
    rtree = connection.execute("SELECT COUNT(*) AS count FROM lidar_source_bounds b JOIN lidar_sources s ON s.id=b.id WHERE s.root_id=?", (root_id,)).fetchone()
    existing_created = connection.execute("SELECT value FROM catalog_meta WHERE key='creation_time'").fetchone()
    creation_time = existing_created["value"] if existing_created is not None else utc_now_iso()
    meta = {
        "schema_version": str(CATALOG_SCHEMA_VERSION),
        "repository_root": str(root),
        "normalized_repository_root": str(root.resolve() if root.exists() else root.absolute()),
        "repository_fingerprint": root_id,
        "creation_time": creation_time,
        "last_update_time": utc_now_iso(),
        "plugin_version": _plugin_version(),
        "header_reader_version": "las-public-header-v1",
        "source_count": str(source_count if source_count is not None else int(row["sources"] or 0)),
        "usable_spatial_source_count": str(int(rtree["count"] or 0)),
        "rtree_row_count": str(int(rtree["count"] or 0)),
        "failed_metadata_count": str(int(row["errors"] or 0)),
    }
    connection.executemany("INSERT OR REPLACE INTO catalog_meta(key, value) VALUES (?, ?)", tuple(meta.items()))


def inspect_catalog_integrity(catalog_path: Path | str, root_path: Path | str) -> CatalogIntegrityReport:
    catalog = Path(catalog_path)
    root = Path(root_path).expanduser()
    root_id = stable_root_id(root)
    if not catalog.exists():
        return CatalogIntegrityReport(catalog, root, root_id, "Empty", False, False, False, False, messages=("Catalog file was not found.",))
    try:
        connection = sqlite3.connect(str(catalog))
        connection.row_factory = sqlite3.Row
        connection.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        return CatalogIntegrityReport(catalog, root, root_id, "Unusable", False, False, False, False, messages=(f"SQLite could not open catalog: {exc}",))
    try:
        schema_valid = _has_table(connection, "lidar_sources") and _has_table(connection, "lidar_source_bounds")
        metadata_valid = _has_table(connection, "catalog_meta")
        if not schema_valid:
            return CatalogIntegrityReport(catalog, root, root_id, "Unusable", True, False, metadata_valid, False, messages=("Catalog schema is incomplete.",))
        identity = _read_identity(connection, root)
        override = read_repository_crs_override_from_connection(connection)
        repository_root_matches = identity.repository_fingerprint == root_id if identity is not None else True
        rows = connection.execute("SELECT s.*, CASE WHEN b.id IS NULL THEN 0 ELSE 1 END AS has_rtree FROM lidar_sources s LEFT JOIN lidar_source_bounds b ON b.id=s.id WHERE s.root_id=?", (root_id,)).fetchall()
        source_count = len(rows)
        enabled = sum(1 for row in rows if str(row["inventory_status"]) == "indexed")
        valid_bounds = sum(1 for row in rows if _row_has_valid_bounds(row))
        missing_rtree = sum(1 for row in rows if str(row["inventory_status"]) == "indexed" and _row_has_valid_bounds(row) and not bool(row["has_rtree"]))
        malformed = sum(1 for row in rows if str(row["inventory_status"]) == "indexed" and not _row_has_valid_bounds(row))
        missing_files = sum(1 for row in rows if str(row["inventory_status"]) != "deleted" and not Path(str(row["source_path"])).exists())
        stale_files = sum(1 for row in rows if _row_is_stale(row))
        rtree_count = int(connection.execute("SELECT COUNT(*) AS count FROM lidar_source_bounds b JOIN lidar_sources s ON s.id=b.id WHERE s.root_id=?", (root_id,)).fetchone()["count"] or 0)
        orphan_rtree = int(connection.execute("SELECT COUNT(*) AS count FROM lidar_source_bounds b LEFT JOIN lidar_sources s ON s.id=b.id WHERE s.id IS NULL").fetchone()["count"] or 0)
        duplicate_paths = int(connection.execute("SELECT COUNT(*) AS count FROM (SELECT source_path FROM lidar_sources WHERE root_id=? GROUP BY source_path HAVING COUNT(*)>1)", (root_id,)).fetchone()["count"] or 0)
        duplicate_ids = int(connection.execute("SELECT COUNT(*) AS count FROM (SELECT source_id FROM lidar_sources WHERE root_id=? GROUP BY source_id HAVING COUNT(*)>1)", (root_id,)).fetchone()["count"] or 0)
        crs_distribution = _crs_distribution(connection, root_id)
        extent = _extent_union(connection, root_id)
        skips = _skip_counts(rows, missing_rtree=missing_rtree, orphan_rtree=orphan_rtree)
        embedded_known = sum(1 for row in rows if str(row["inventory_status"]) == "indexed" and _row_has_valid_bounds(row) and str(row["source_crs"] or "").strip())
        crs_unknown_bounded = sum(1 for row in rows if str(row["inventory_status"]) == "indexed" and _row_has_valid_bounds(row) and not str(row["source_crs"] or "").strip())
        effective_known = embedded_known + (crs_unknown_bounded if override is not None else 0)
        effective_unknown = max(0, valid_bounds - effective_known)
        if override is not None:
            skips = {key: value for key, value in skips.items() if key != SKIP_CRS_MISSING}
        if not repository_root_matches:
            status = "Unusable"
            messages = ("Catalog identity does not match the selected repository.",)
        elif source_count == 0:
            status = "Empty"
            messages = ("Catalog has no source records for this repository.",)
        elif rtree_count == 0:
            status = "Unusable"
            messages = ("Catalog records exist but no usable spatial index rows are present.",)
        elif missing_rtree or orphan_rtree or malformed or missing_files or stale_files:
            status = "Needs Repair"
            messages = ("Catalog has integrity issues; repair or refresh before critical processing.",)
        elif valid_bounds and effective_known == 0:
            status = "CRS Assignment Required"
            messages = ("LiDAR files were indexed, but their coordinate system is unknown. Coverage cannot yet be compared with the selected polygon.",)
        elif override is not None:
            status = "Healthy with validated repository CRS override"
            messages = (f"Catalog is spatially usable with repository CRS override {override.crs}.",)
        elif effective_unknown:
            status = "Incomplete"
            messages = ("Some bounded source records still lack an effective CRS.",)
        else:
            status = "Healthy"
            messages = ("Catalog is spatially usable.",)
        return CatalogIntegrityReport(catalog, root, root_id, status, True, schema_valid, metadata_valid, repository_root_matches, source_count, enabled, valid_bounds, rtree_count, missing_rtree, orphan_rtree, duplicate_paths, duplicate_ids, malformed, stale_files, missing_files, crs_distribution, extent, skips, messages, identity, embedded_known, crs_unknown_bounded, effective_known, effective_unknown, None if override is None else override.crs)
    finally:
        connection.close()


def repair_catalog(catalog_path: Path | str, root_path: Path | str, *, create_backup: bool = True) -> CatalogRepairReport:
    before = inspect_catalog_integrity(catalog_path, root_path)
    catalog = Path(catalog_path)
    operations: list[str] = []
    backup: Path | None = None
    if not catalog.exists() or not before.sqlite_opens:
        return CatalogRepairReport(catalog, None, before, before, (), False, before.preflight_blocker_message() or "Catalog cannot be repaired because it does not open.")
    if create_backup:
        backup = catalog.with_name(f"{catalog.stem}.backup-{utc_now_iso().replace(':', '').replace('+', 'Z')}{catalog.suffix}")
        shutil.copy2(catalog, backup)
        operations.append(f"Backup created: {backup}")
    connection = connect_catalog(catalog)
    root_id = stable_root_id(root_path)
    try:
        orphan_ids = [int(row["id"]) for row in connection.execute("SELECT b.id FROM lidar_source_bounds b LEFT JOIN lidar_sources s ON s.id=b.id WHERE s.id IS NULL").fetchall()]
        if orphan_ids:
            connection.executemany("DELETE FROM lidar_source_bounds WHERE id=?", ((item,) for item in orphan_ids))
            operations.append(f"Removed {len(orphan_ids):,} orphan RTree row(s).")
        rows = connection.execute("SELECT s.*, b.id AS rtree_id FROM lidar_sources s LEFT JOIN lidar_source_bounds b ON b.id=s.id WHERE s.root_id=? AND s.inventory_status='indexed'", (root_id,)).fetchall()
        rebuilt = 0
        invalid_removed = 0
        for row in rows:
            if _row_has_valid_bounds(row):
                if row["rtree_id"] is None:
                    connection.execute("INSERT OR REPLACE INTO lidar_source_bounds(id, xmin, xmax, ymin, ymax) VALUES (?, ?, ?, ?, ?)", (int(row["id"]), float(row["xmin"]), float(row["xmax"]), float(row["ymin"]), float(row["ymax"])))
                    rebuilt += 1
            elif row["rtree_id"] is not None:
                connection.execute("DELETE FROM lidar_source_bounds WHERE id=?", (int(row["id"]),))
                invalid_removed += 1
        if rebuilt:
            operations.append(f"Rebuilt {rebuilt:,} missing RTree entr{'y' if rebuilt == 1 else 'ies'}.")
        if invalid_removed:
            operations.append(f"Removed {invalid_removed:,} invalid RTree entr{'y' if invalid_removed == 1 else 'ies'}.")
        missing = [int(row["id"]) for row in connection.execute("SELECT id, source_path FROM lidar_sources WHERE root_id=? AND inventory_status!='deleted'", (root_id,)).fetchall() if not Path(str(row["source_path"])).exists()]
        if missing:
            connection.executemany("UPDATE lidar_sources SET inventory_status='deleted', metadata_error='FILE_MISSING' WHERE id=?", ((item,) for item in missing))
            connection.executemany("DELETE FROM lidar_source_bounds WHERE id=?", ((item,) for item in missing))
            operations.append(f"Marked {len(missing):,} missing file record(s) as deleted.")
        write_catalog_identity(connection, root_path)
        connection.commit()
    finally:
        connection.close()
    after = inspect_catalog_integrity(catalog, root_path)
    repaired = after.status in {"Healthy", "Healthy with validated repository CRS override", "Needs Repair", "CRS Assignment Required"} and after.rtree_row_count >= before.rtree_row_count
    message = "Catalog repair completed. " + " ".join(operations or ("No structural repairs were needed.",))
    return CatalogRepairReport(catalog, backup, before, after, tuple(operations), repaired, message)


def source_view_rows(catalog_path: Path | str, root_path: Path | str, *, status_filter: str = "all", polygon_extent: Bounds2D | None = None, limit: int = 500) -> tuple[RepositorySourceViewRow, ...]:
    report = inspect_catalog_integrity(catalog_path, root_path)
    if not report.sqlite_opens or not report.schema_valid:
        return ()
    connection = sqlite3.connect(str(catalog_path))
    connection.row_factory = sqlite3.Row
    root_id = stable_root_id(root_path)
    try:
        rows = connection.execute("SELECT s.*, CASE WHEN b.id IS NULL THEN 0 ELSE 1 END AS has_rtree FROM lidar_sources s LEFT JOIN lidar_source_bounds b ON b.id=s.id WHERE s.root_id=? ORDER BY s.relative_path LIMIT ?", (root_id, int(limit))).fetchall()
        out: list[RepositorySourceViewRow] = []
        for row in rows:
            problem = _row_problem(row)
            if not _row_matches_filter(row, problem, status_filter, polygon_extent):
                continue
            embedded = str(row["source_crs"] or "")
            effective = embedded or (report.repository_crs_override or "")
            crs_source = "embedded" if embedded else ("repository_override" if report.repository_crs_override else "unknown")
            out.append(RepositorySourceViewRow(Path(str(row["source_path"])).name, str(row["source_type"]), str(row["inventory_status"]), effective or "unknown", embedded or "unknown", effective or "unknown", crs_source, _float_or_none(row["xmin"]), _float_or_none(row["xmax"]), _float_or_none(row["ymin"]), _float_or_none(row["ymax"]), None if row["point_count"] is None else int(row["point_count"]), int(row["modified_time_ns"] or 0), problem, bool(row["has_rtree"])))
        return tuple(out)
    finally:
        connection.close()


def assign_repository_crs_override(catalog_path: Path | str, root_path: Path | str, crs: str, *, assigned_by: str = "user", method: str = "qgis_crs_selector", note: str = "") -> RepositoryCrsOverride:
    value = (crs or "").strip()
    if not value:
        raise ValueError("Repository CRS override requires a CRS value.")
    connection = connect_catalog(catalog_path)
    try:
        override = RepositoryCrsOverride(value, utc_now_iso(), assigned_by, method, note)
        payload = {
            "repository_crs_override": override.crs,
            "repository_crs_override_assigned_at": override.assigned_at,
            "repository_crs_override_assigned_by": override.assigned_by,
            "repository_crs_override_method": override.method,
            "repository_crs_override_note": override.note,
        }
        connection.executemany("INSERT OR REPLACE INTO catalog_meta(key, value) VALUES (?, ?)", tuple(payload.items()))
        write_catalog_identity(connection, root_path)
        connection.commit()
        return override
    finally:
        connection.close()


def remove_repository_crs_override(catalog_path: Path | str, root_path: Path | str) -> None:
    connection = connect_catalog(catalog_path)
    try:
        connection.execute("DELETE FROM catalog_meta WHERE key LIKE 'repository_crs_override%'")
        write_catalog_identity(connection, root_path)
        connection.commit()
    finally:
        connection.close()


def read_repository_crs_override(catalog_path: Path | str) -> RepositoryCrsOverride | None:
    connection = connect_catalog(catalog_path)
    try:
        return read_repository_crs_override_from_connection(connection)
    finally:
        connection.close()


def read_repository_crs_override_from_connection(connection: sqlite3.Connection) -> RepositoryCrsOverride | None:
    if not _has_table(connection, "catalog_meta"):
        return None
    meta = {str(row["key"]): str(row["value"]) for row in connection.execute("SELECT key, value FROM catalog_meta WHERE key LIKE 'repository_crs_override%'").fetchall()}
    crs = meta.get("repository_crs_override")
    if not crs:
        return None
    return RepositoryCrsOverride(crs, meta.get("repository_crs_override_assigned_at", ""), meta.get("repository_crs_override_assigned_by", "user"), meta.get("repository_crs_override_method", "unknown"), meta.get("repository_crs_override_note", ""))


def inspect_catalog_records(catalog_path: Path | str, root_path: Path | str, *, sample_size: int = 10) -> CatalogRecordInspectionReport:
    report = inspect_catalog_integrity(catalog_path, root_path)
    if not report.sqlite_opens or not report.schema_valid:
        return CatalogRecordInspectionReport(Path(catalog_path), Path(root_path), Path(root_path), report.root_id, 0, 0, (), (), (), (), None, None)
    connection = sqlite3.connect(str(catalog_path))
    connection.row_factory = sqlite3.Row
    try:
        root_id = stable_root_id(root_path)
        rows = connection.execute("SELECT * FROM lidar_sources WHERE root_id=? ORDER BY relative_path", (root_id,)).fetchall()
        first = tuple(Path(str(row["source_path"])) for row in rows[:10])
        last = tuple(Path(str(row["source_path"])) for row in rows[-10:])
        step = max(1, len(rows) // max(1, sample_size))
        sample = tuple(Path(str(row["source_path"])) for row in rows[::step][:sample_size])
        extent_sources = tuple(_extent_defining_sources(connection, root_id))
        created = connection.execute("SELECT value FROM catalog_meta WHERE key='creation_time'").fetchone()
        updated = connection.execute("SELECT value FROM catalog_meta WHERE key='last_update_time'").fetchone()
        identity_root = report.identity.normalized_repository_root if report.identity is not None else Path(root_path)
        return CatalogRecordInspectionReport(Path(catalog_path), identity_root, Path(root_path), report.root_id, len(rows), report.rtree_row_count, first, last, sample, extent_sources, None if created is None else str(created["value"]), None if updated is None else str(updated["value"]))
    finally:
        connection.close()


def _extent_defining_sources(connection: sqlite3.Connection, root_id: str) -> tuple[ExtentDefiningSource, ...]:
    specs = (("minimum_x", "xmin", "ASC"), ("maximum_x", "xmax", "DESC"), ("minimum_y", "ymin", "ASC"), ("maximum_y", "ymax", "DESC"))
    out: list[ExtentDefiningSource] = []
    for role, column, direction in specs:
        row = connection.execute(f"SELECT s.source_path, s.source_id, b.{column} AS value FROM lidar_source_bounds b JOIN lidar_sources s ON s.id=b.id WHERE s.root_id=? ORDER BY b.{column} {direction} LIMIT 1", (root_id,)).fetchone()
        if row is not None:
            out.append(ExtentDefiningSource(role, Path(str(row["source_path"])), float(row["value"]), str(row["source_id"])))
    return tuple(out)


def _read_identity(connection: sqlite3.Connection, root: Path) -> CatalogIdentity | None:
    if not _has_table(connection, "catalog_meta"):
        return None
    meta = {str(row["key"]): str(row["value"]) for row in connection.execute("SELECT key, value FROM catalog_meta").fetchall()}
    normalized = Path(meta.get("normalized_repository_root") or (root.resolve() if root.exists() else root.absolute()))
    return CatalogIdentity(
        schema_version=_int_or_none(meta.get("schema_version")),
        repository_root=Path(meta.get("repository_root") or root),
        normalized_repository_root=normalized,
        repository_fingerprint=meta.get("repository_fingerprint") or stable_root_id(root),
        creation_time=meta.get("creation_time"),
        last_update_time=meta.get("last_update_time"),
        plugin_version=meta.get("plugin_version", "unknown"),
        header_reader_version=meta.get("header_reader_version", "unknown"),
        source_count=_int_or_none(meta.get("source_count")) or 0,
        usable_spatial_source_count=_int_or_none(meta.get("usable_spatial_source_count")) or 0,
        rtree_row_count=_int_or_none(meta.get("rtree_row_count")) or 0,
        failed_metadata_count=_int_or_none(meta.get("failed_metadata_count")) or 0,
        repository_crs_override=meta.get("repository_crs_override"),
        crs_override_source=meta.get("repository_crs_override_method"),
    )


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table','virtual table') AND name=?", (name,)).fetchone()
    return row is not None


def _row_has_valid_bounds(row: sqlite3.Row) -> bool:
    values = [_float_or_none(row[key]) for key in ("xmin", "xmax", "ymin", "ymax")]
    if any(value is None for value in values):
        return False
    xmin, xmax, ymin, ymax = values  # type: ignore[misc]
    if not all(math.isfinite(float(value)) for value in values if value is not None):
        return False
    if float(xmin) >= float(xmax) or float(ymin) >= float(ymax):
        return False
    if all(abs(float(value)) < 1e-12 for value in values if value is not None):
        return False
    if any(abs(float(value)) > 1e12 for value in values if value is not None):
        return False
    return True


def _row_problem(row: sqlite3.Row) -> str:
    status = str(row["inventory_status"])
    if status == "error":
        return str(row["metadata_error"] or SKIP_HEADER_READ_FAILED)
    if status == "deleted":
        return SKIP_FILE_MISSING
    if not Path(str(row["source_path"])).exists():
        return SKIP_FILE_MISSING
    if not _row_has_valid_bounds(row):
        if any(row[key] is None for key in ("xmin", "xmax", "ymin", "ymax")):
            return SKIP_BOUNDS_MISSING
        values = [_float_or_none(row[key]) for key in ("xmin", "xmax", "ymin", "ymax")]
        if any(value is None or not math.isfinite(float(value)) for value in values):
            return SKIP_BOUNDS_NONFINITE
        return SKIP_BOUNDS_INVALID
    if not bool(row["has_rtree"]):
        return SKIP_RTREE_ENTRY_MISSING
    if not str(row["source_crs"] or "").strip():
        return SKIP_CRS_MISSING
    if _row_is_stale(row):
        return SKIP_FILE_CHANGED
    return ""


def _row_is_stale(row: sqlite3.Row) -> bool:
    path = Path(str(row["source_path"]))
    if not path.exists():
        return False
    try:
        stat = path.stat()
    except OSError:
        return True
    return int(row["file_size"] or 0) != int(stat.st_size) or int(row["modified_time_ns"] or 0) != int(stat.st_mtime_ns)


def _skip_counts(rows: list[sqlite3.Row], *, missing_rtree: int, orphan_rtree: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        problem = _row_problem(row)
        if problem:
            code = _classify_problem(problem)
            counts[code] = counts.get(code, 0) + 1
    if missing_rtree:
        counts[SKIP_RTREE_ENTRY_MISSING] = max(counts.get(SKIP_RTREE_ENTRY_MISSING, 0), missing_rtree)
    if orphan_rtree:
        counts[SKIP_RTREE_ENTRY_INVALID] = orphan_rtree
    return counts


def _classify_problem(problem: str) -> str:
    upper = problem.upper()
    if "RTREE" in upper:
        return SKIP_RTREE_ENTRY_MISSING
    if "CRS" in upper:
        return SKIP_CRS_MISSING
    if "BOUND" in upper:
        return SKIP_BOUNDS_INVALID
    if "MISSING" in upper or "FILE" in upper:
        return SKIP_FILE_MISSING
    if "CHANGED" in upper or "STALE" in upper:
        return SKIP_FILE_CHANGED
    return SKIP_HEADER_READ_FAILED


def _crs_distribution(connection: sqlite3.Connection, root_id: str) -> dict[str, int]:
    rows = connection.execute("SELECT COALESCE(NULLIF(source_crs,''), 'unknown') AS crs, COUNT(*) AS count FROM lidar_sources WHERE root_id=? GROUP BY COALESCE(NULLIF(source_crs,''), 'unknown')", (root_id,)).fetchall()
    return {str(row["crs"]): int(row["count"] or 0) for row in rows}


def _extent_union(connection: sqlite3.Connection, root_id: str) -> Bounds2D | None:
    row = connection.execute("SELECT MIN(b.xmin) AS xmin, MAX(b.xmax) AS xmax, MIN(b.ymin) AS ymin, MAX(b.ymax) AS ymax FROM lidar_source_bounds b JOIN lidar_sources s ON s.id=b.id WHERE s.root_id=?", (root_id,)).fetchone()
    if row is None or row["xmin"] is None:
        return None
    return Bounds2D(float(row["xmin"]), float(row["ymin"]), float(row["xmax"]), float(row["ymax"]))


def _row_matches_filter(row: sqlite3.Row, problem: str, status_filter: str, polygon_extent: Bounds2D | None) -> bool:
    if status_filter == "all":
        return True
    if status_filter == "usable":
        return not problem or problem == SKIP_CRS_MISSING
    if status_filter == "header_errors":
        return str(row["inventory_status"]) == "error"
    if status_filter == "missing_crs":
        return not str(row["source_crs"] or "").strip()
    if status_filter == "invalid_bounds":
        return problem in {SKIP_BOUNDS_INVALID, SKIP_BOUNDS_MISSING, SKIP_BOUNDS_NONFINITE}
    if status_filter == "missing_files":
        return problem == SKIP_FILE_MISSING
    if status_filter == "outside_current_polygon" and polygon_extent is not None and _row_has_valid_bounds(row):
        return not Bounds2D(float(row["xmin"]), float(row["ymin"]), float(row["xmax"]), float(row["ymax"])).intersects(polygon_extent)
    return False


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _plugin_version() -> str:
    try:
        from pyforestscan_qgis.__version__ import __version__

        return str(__version__)
    except Exception:
        return "unknown"
