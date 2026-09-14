"""SQLite/RTree LiDAR spatial catalog storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .lidar_catalog_models import CATALOG_SCHEMA_VERSION, LidarCatalogRecord, LidarCatalogSummary


def connect_catalog(catalog_path: Path | str) -> sqlite3.Connection:
    """Open a catalog connection and ensure schema exists."""
    path = Path(catalog_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    initialize_catalog(connection)
    return connection


def initialize_catalog(connection: sqlite3.Connection) -> None:
    """Create catalog tables and indexes."""
    connection.executescript(
        f"""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS catalog_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR REPLACE INTO catalog_meta(key, value) VALUES ('schema_version', '{CATALOG_SCHEMA_VERSION}');
        CREATE TABLE IF NOT EXISTS lidar_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            source_type TEXT NOT NULL,
            xmin REAL,
            xmax REAL,
            ymin REAL,
            ymax REAL,
            zmin REAL,
            zmax REAL,
            source_crs TEXT,
            point_count INTEGER,
            file_size INTEGER NOT NULL DEFAULT 0,
            modified_time_ns INTEGER NOT NULL DEFAULT 0,
            header_signature TEXT NOT NULL DEFAULT '',
            inventory_status TEXT NOT NULL DEFAULT 'indexed',
            metadata_error TEXT,
            indexed_at TEXT NOT NULL DEFAULT '',
            root_id TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS lidar_source_bounds USING rtree(
            id,
            xmin,
            xmax,
            ymin,
            ymax
        );
        CREATE INDEX IF NOT EXISTS idx_lidar_sources_relative_path ON lidar_sources(relative_path);
        CREATE INDEX IF NOT EXISTS idx_lidar_sources_source_type ON lidar_sources(source_type);
        CREATE INDEX IF NOT EXISTS idx_lidar_sources_modified ON lidar_sources(modified_time_ns);
        CREATE INDEX IF NOT EXISTS idx_lidar_sources_root ON lidar_sources(root_id);
        CREATE INDEX IF NOT EXISTS idx_lidar_sources_status ON lidar_sources(inventory_status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_lidar_sources_root_relative ON lidar_sources(root_id, relative_path);
        """
    )
    connection.commit()


def upsert_records(connection: sqlite3.Connection, records: Iterable[LidarCatalogRecord]) -> int:
    """Insert or update records and maintain the RTree."""
    count = 0
    for record in records:
        connection.execute(
            """
            INSERT INTO lidar_sources(
                source_id, source_path, relative_path, source_type, xmin, xmax, ymin, ymax, zmin, zmax,
                source_crs, point_count, file_size, modified_time_ns, header_signature, inventory_status,
                metadata_error, indexed_at, root_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_path=excluded.source_path,
                relative_path=excluded.relative_path,
                source_type=excluded.source_type,
                xmin=excluded.xmin,
                xmax=excluded.xmax,
                ymin=excluded.ymin,
                ymax=excluded.ymax,
                zmin=excluded.zmin,
                zmax=excluded.zmax,
                source_crs=excluded.source_crs,
                point_count=excluded.point_count,
                file_size=excluded.file_size,
                modified_time_ns=excluded.modified_time_ns,
                header_signature=excluded.header_signature,
                inventory_status=excluded.inventory_status,
                metadata_error=excluded.metadata_error,
                indexed_at=excluded.indexed_at,
                root_id=excluded.root_id
            """,
            _record_values(record),
        )
        row = connection.execute("SELECT id FROM lidar_sources WHERE source_id = ?", (record.source_id,)).fetchone()
        if row is not None:
            connection.execute("DELETE FROM lidar_source_bounds WHERE id = ?", (int(row["id"]),))
            if record.inventory_status == "indexed" and record.has_bounds:
                connection.execute(
                    "INSERT OR REPLACE INTO lidar_source_bounds(id, xmin, xmax, ymin, ymax) VALUES (?, ?, ?, ?, ?)",
                    (int(row["id"]), record.xmin, record.xmax, record.ymin, record.ymax),
                )
        count += 1
    return count


def record_for_relative_path(connection: sqlite3.Connection, root_id: str, relative_path: str) -> LidarCatalogRecord | None:
    row = connection.execute("SELECT * FROM lidar_sources WHERE root_id = ? AND relative_path = ?", (root_id, relative_path)).fetchone()
    return _row_to_record(row) if row is not None else None



def query_intersecting_records(connection: sqlite3.Connection, root_id: str, xmin: float, xmax: float, ymin: float, ymax: float, *, limit: int | None = None) -> tuple[LidarCatalogRecord, ...]:
    sql = """
        SELECT s.*
        FROM lidar_source_bounds b
        JOIN lidar_sources s ON s.id = b.id
        WHERE s.root_id = ?
          AND s.inventory_status = 'indexed'
          AND b.xmin <= ? AND b.xmax >= ?
          AND b.ymin <= ? AND b.ymax >= ?
        ORDER BY s.relative_path
    """
    params: tuple[object, ...] = (root_id, xmax, xmin, ymax, ymin)
    if limit is not None:
        sql += " LIMIT ?"
        params = (*params, int(limit))
    return tuple(_row_to_record(row) for row in connection.execute(sql, params).fetchall())


def catalog_summary(catalog_path: Path | str, root_path: Path | str) -> LidarCatalogSummary:
    path = Path(catalog_path)
    from .lidar_catalog_models import stable_root_id

    root = Path(root_path)
    root_id = stable_root_id(root)
    if not path.exists():
        return LidarCatalogSummary(path, root, root_id, False)
    connection = connect_catalog(path)
    try:
        row = connection.execute(
            """
            SELECT
              COUNT(*) AS source_count,
              SUM(CASE WHEN inventory_status = 'indexed' THEN 1 ELSE 0 END) AS indexed_count,
              SUM(CASE WHEN inventory_status = 'error' THEN 1 ELSE 0 END) AS error_count,
              SUM(CASE WHEN inventory_status = 'deleted' THEN 1 ELSE 0 END) AS deleted_count,
              MAX(indexed_at) AS last_indexed_at
            FROM lidar_sources WHERE root_id = ?
            """,
            (root_id,),
        ).fetchone()
        version_row = connection.execute("SELECT value FROM catalog_meta WHERE key = 'schema_version'").fetchone()
        return LidarCatalogSummary(
            catalog_path=path,
            root_path=root,
            root_id=root_id,
            exists=True,
            source_count=int(row["source_count"] or 0),
            indexed_count=int(row["indexed_count"] or 0),
            error_count=int(row["error_count"] or 0),
            deleted_count=int(row["deleted_count"] or 0),
            last_indexed_at=row["last_indexed_at"],
            schema_version=int(version_row["value"]) if version_row is not None else None,
        )
    finally:
        connection.close()


def _record_values(record: LidarCatalogRecord) -> tuple[object, ...]:
    return (
        record.source_id,
        str(record.source_path),
        record.relative_path,
        record.source_type,
        record.xmin,
        record.xmax,
        record.ymin,
        record.ymax,
        record.zmin,
        record.zmax,
        record.source_crs,
        record.point_count,
        record.file_size,
        record.modified_time_ns,
        record.header_signature,
        record.inventory_status,
        record.metadata_error,
        record.indexed_at,
        record.root_id,
    )


def _row_to_record(row: sqlite3.Row) -> LidarCatalogRecord:
    return LidarCatalogRecord(
        source_id=str(row["source_id"]),
        source_path=Path(str(row["source_path"])),
        relative_path=str(row["relative_path"]),
        source_type=str(row["source_type"]),
        xmin=row["xmin"],
        xmax=row["xmax"],
        ymin=row["ymin"],
        ymax=row["ymax"],
        zmin=row["zmin"],
        zmax=row["zmax"],
        source_crs=row["source_crs"],
        point_count=row["point_count"],
        file_size=int(row["file_size"] or 0),
        modified_time_ns=int(row["modified_time_ns"] or 0),
        header_signature=str(row["header_signature"] or ""),
        inventory_status=str(row["inventory_status"] or ""),
        metadata_error=row["metadata_error"],
        indexed_at=str(row["indexed_at"] or ""),
        root_id=str(row["root_id"] or ""),
    )
