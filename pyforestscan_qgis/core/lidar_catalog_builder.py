"""Streaming LiDAR catalog builder with header-only metadata inspection."""

from __future__ import annotations

import fnmatch
import json
import os
import struct
from pathlib import Path
from typing import Callable, Iterable

from .lidar_catalog import connect_catalog, record_for_relative_path, upsert_records
from .lidar_catalog_models import CatalogBuildOptions, LidarCatalogBuildResult, LidarCatalogRecord, default_lidar_catalog_path, source_id_for, stable_root_id, utc_now_iso
from .lidar_inventory import lidar_source_type

ProgressCallback = Callable[[dict[str, int | str]], None]
CancelCallback = Callable[[], bool]


def build_lidar_catalog(
    root_path: Path | str,
    catalog_path: Path | str | None = None,
    *,
    options: CatalogBuildOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
    inspector: Callable[[Path, Path, str], LidarCatalogRecord] | None = None,
) -> LidarCatalogBuildResult:
    """Build or update a persistent catalog using streaming traversal and batched commits."""
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"LiDAR repository does not exist: {root}")
    options = options or CatalogBuildOptions()
    catalog = Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(root)
    root_id = stable_root_id(root)
    inspect = inspector or inspect_lidar_header
    connection = connect_catalog(catalog)
    discovered = indexed = unchanged = updated = errors = deleted = 0
    seen_batch: list[str] = []
    batch: list[LidarCatalogRecord] = []
    cancelled = False
    try:
        if progress_callback is not None:
            progress_callback({"stage": "Preparing", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted})
        connection.execute("DROP TABLE IF EXISTS temp_seen_paths")
        connection.execute("CREATE TEMP TABLE temp_seen_paths(relative_path TEXT PRIMARY KEY)")
        for path in iter_lidar_paths(root, options=options):
            if cancel_callback is not None and cancel_callback():
                cancelled = True
                break
            discovered += 1
            relative = path.relative_to(root).as_posix()
            latest_source = relative
            seen_batch.append(relative)
            previous = record_for_relative_path(connection, root_id, relative)
            try:
                stat = path.stat()
            except OSError:
                continue
            if previous is not None and previous.file_size == int(stat.st_size) and previous.modified_time_ns == int(stat.st_mtime_ns) and previous.inventory_status == "indexed":
                unchanged += 1
            else:
                record = inspect(path, root, root_id)
                if record.inventory_status == "indexed":
                    indexed += 1
                elif record.inventory_status == "error":
                    errors += 1
                if previous is not None:
                    updated += 1
                batch.append(record)
            if len(batch) >= options.thresholds.batch_commit_size:
                if progress_callback is not None:
                    progress_callback({"stage": "Writing Spatial Index", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted, "latest_source": latest_source})
                upsert_records(connection, batch)
                batch.clear()
            if len(seen_batch) >= options.thresholds.batch_commit_size:
                connection.executemany("INSERT OR IGNORE INTO temp_seen_paths(relative_path) VALUES (?)", ((item,) for item in seen_batch))
                seen_batch.clear()
                connection.commit()
            if options.max_source_files is not None and discovered >= options.max_source_files:
                cancelled = True
                break
            if progress_callback is not None and discovered % options.thresholds.checkpoint_interval == 0:
                progress_callback({"stage": "Reading Metadata", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted, "latest_source": latest_source})
        if batch:
            upsert_records(connection, batch)
        if seen_batch:
            connection.executemany("INSERT OR IGNORE INTO temp_seen_paths(relative_path) VALUES (?)", ((item,) for item in seen_batch))
            seen_batch.clear()
        connection.commit()
        if not cancelled:
            if progress_callback is not None:
                progress_callback({"stage": "Detecting Deleted Sources", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted})
            deleted_rows = connection.execute(
                "SELECT id FROM lidar_sources WHERE root_id = ? AND relative_path NOT IN (SELECT relative_path FROM temp_seen_paths) AND inventory_status != 'deleted'",
                (root_id,),
            ).fetchall()
            deleted_ids = [int(row["id"]) for row in deleted_rows]
            connection.execute(
                "UPDATE lidar_sources SET inventory_status = 'deleted' WHERE root_id = ? AND relative_path NOT IN (SELECT relative_path FROM temp_seen_paths)",
                (root_id,),
            )
            connection.executemany("DELETE FROM lidar_source_bounds WHERE id = ?", ((item,) for item in deleted_ids))
            deleted = len(deleted_ids)
            connection.commit()
        if progress_callback is not None:
            progress_callback({"stage": "Verifying Catalog", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted})
            progress_callback({"stage": "Finalizing", "discovered": discovered, "indexed": indexed, "errors": errors, "unchanged": unchanged, "deleted": deleted})
    finally:
        connection.close()
    return LidarCatalogBuildResult(catalog, root, root_id, discovered, indexed, unchanged, updated, errors, deleted, cancelled)


def iter_lidar_paths(root_path: Path | str, *, options: CatalogBuildOptions | None = None) -> Iterable[Path]:
    """Yield supported LiDAR source paths without materializing the full tree."""
    root = Path(root_path).expanduser().resolve()
    options = options or CatalogBuildOptions()
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.parts) - root_depth
        if options.max_depth is not None and depth >= options.max_depth:
            dirnames[:] = []
        if options.ignore_hidden:
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            filenames = [name for name in filenames if not name.startswith(".")]
        if options.ignore_names:
            ignored = set(options.ignore_names)
            dirnames[:] = [name for name in dirnames if name not in ignored]
        for filename in filenames:
            path = current / filename
            source_type = lidar_source_type(path, include_ept=True)
            if source_type is None:
                continue
            if options.source_types and source_type not in options.source_types:
                continue
            rel = path.relative_to(root).as_posix()
            if options.include_globs and not any(fnmatch.fnmatch(rel, pattern) for pattern in options.include_globs):
                continue
            if options.exclude_globs and any(fnmatch.fnmatch(rel, pattern) for pattern in options.exclude_globs):
                continue
            yield path
        if not options.recursive:
            dirnames[:] = []


def inspect_lidar_header(path: Path, root: Path, root_id: str) -> LidarCatalogRecord:
    """Inspect source metadata without reading point arrays."""
    source_type = lidar_source_type(path, include_ept=True) or "unknown"
    stat = path.stat()
    relative = path.relative_to(root).as_posix()
    source_id = source_id_for(root_id, relative)
    try:
        if source_type == "ept":
            metadata = _inspect_ept(path)
        else:
            metadata = _inspect_las_public_header(path)
        signature = _header_signature(stat.st_size, stat.st_mtime_ns, metadata)
        return LidarCatalogRecord(
            source_id=source_id,
            source_path=path,
            relative_path=relative,
            source_type=source_type,
            xmin=metadata.get("xmin"),
            xmax=metadata.get("xmax"),
            ymin=metadata.get("ymin"),
            ymax=metadata.get("ymax"),
            zmin=metadata.get("zmin"),
            zmax=metadata.get("zmax"),
            source_crs=metadata.get("crs"),
            point_count=metadata.get("point_count"),
            file_size=int(stat.st_size),
            modified_time_ns=int(stat.st_mtime_ns),
            header_signature=signature,
            inventory_status="indexed",
            metadata_error=None,
            indexed_at=utc_now_iso(),
            root_id=root_id,
        )
    except Exception as exc:  # noqa: BLE001 - metadata failures must be recorded, not hidden.
        return LidarCatalogRecord(
            source_id=source_id,
            source_path=path,
            relative_path=relative,
            source_type=source_type,
            file_size=int(stat.st_size),
            modified_time_ns=int(stat.st_mtime_ns),
            header_signature=f"{stat.st_size}:{stat.st_mtime_ns}:error",
            inventory_status="error",
            metadata_error=str(exc),
            indexed_at=utc_now_iso(),
            root_id=root_id,
        )


def _inspect_ept(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    bounds_value = payload.get("bounds") if isinstance(payload, dict) else None
    if not isinstance(bounds_value, list) or len(bounds_value) < 6:
        raise ValueError("EPT metadata does not include six-value bounds.")
    srs = payload.get("srs") if isinstance(payload, dict) else None
    crs = None
    if isinstance(srs, dict):
        crs = srs.get("authority") or srs.get("horizontal") or srs.get("wkt")
    points = payload.get("points") if isinstance(payload, dict) else None
    return {
        "xmin": float(bounds_value[0]),
        "ymin": float(bounds_value[1]),
        "zmin": float(bounds_value[2]),
        "xmax": float(bounds_value[3]),
        "ymax": float(bounds_value[4]),
        "zmax": float(bounds_value[5]),
        "crs": str(crs) if crs else None,
        "point_count": int(points) if points is not None else None,
    }


def _inspect_las_public_header(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        header = handle.read(375)
    if len(header) < 227 or header[:4] != b"LASF":
        raise ValueError("LAS/LAZ public header is missing or invalid.")
    legacy_points = struct.unpack_from("<I", header, 107)[0]
    point_count = legacy_points
    if len(header) >= 255:
        extended_points = struct.unpack_from("<Q", header, 247)[0]
        if extended_points:
            point_count = int(extended_points)
    x_scale, y_scale, z_scale = struct.unpack_from("<ddd", header, 131)
    x_offset, y_offset, z_offset = struct.unpack_from("<ddd", header, 155)
    max_x, min_x, max_y, min_y, max_z, min_z = struct.unpack_from("<dddddd", header, 179)
    return {
        "xmin": float(min_x),
        "xmax": float(max_x),
        "ymin": float(min_y),
        "ymax": float(max_y),
        "zmin": float(min_z),
        "zmax": float(max_z),
        "point_count": int(point_count),
        "crs": None,
        "scale_signature": f"{x_scale:g},{y_scale:g},{z_scale:g}:{x_offset:g},{y_offset:g},{z_offset:g}",
    }


def _header_signature(size: int, modified_ns: int, metadata: dict[str, object]) -> str:
    return ":".join(
        str(value)
        for value in (
            size,
            modified_ns,
            metadata.get("xmin"),
            metadata.get("xmax"),
            metadata.get("ymin"),
            metadata.get("ymax"),
            metadata.get("zmin"),
            metadata.get("zmax"),
            metadata.get("point_count"),
            metadata.get("scale_signature", ""),
        )
    )
