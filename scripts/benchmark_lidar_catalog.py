#!/usr/bin/env python3
"""Safe LiDAR catalog benchmark/report tool."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.lidar_catalog import connect_catalog, upsert_records
from pyforestscan_qgis.core.lidar_catalog_jobs import CatalogJobRunner, CatalogJobSpec
from pyforestscan_qgis.core.lidar_catalog_models import LidarCatalogRecord, default_lidar_catalog_path, source_id_for, stable_root_id, utc_now_iso
from pyforestscan_qgis.core.lidar_catalog_probe import quick_probe_lidar_repository
from pyforestscan_qgis.core.lidar_catalog_query import query_catalog_for_polygon
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt


def synthetic_benchmark(record_count: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
        root_id = stable_root_id(root)
        now = utc_now_iso()
        records = []
        for index in range(record_count):
            x = float(index % 1000)
            y = float(index // 1000)
            rel = f"tile_{index}.las"
            records.append(
                LidarCatalogRecord(
                    source_id=source_id_for(root_id, rel),
                    source_path=root / rel,
                    relative_path=rel,
                    source_type="las",
                    xmin=x,
                    xmax=x + 0.9,
                    ymin=y,
                    ymax=y + 0.9,
                    zmin=0.0,
                    zmax=10.0,
                    point_count=1000,
                    file_size=100,
                    modified_time_ns=index,
                    header_signature=str(index),
                    indexed_at=now,
                    root_id=root_id,
                )
            )
        connection = connect_catalog(catalog)
        start = time.perf_counter()
        upsert_records(connection, records)
        connection.commit()
        insert_seconds = time.perf_counter() - start
        connection.close()
        polygon = normalized_selection_from_wkt("POLYGON ((10 0, 30 0, 30 20, 10 20, 10 0))", "EPSG:32610")
        query = query_catalog_for_polygon(catalog, root, polygon)
        return {
            "mode": "synthetic",
            "records": record_count,
            "sqlite_write_seconds": round(insert_seconds, 6),
            "sqlite_write_rate_records_per_second": round(record_count / max(insert_seconds, 0.001), 2),
            "query_seconds": round(query.query_seconds, 6),
            "query_matches": len(query.records),
            "catalog_path": str(catalog),
        }


def dry_probe(path: Path) -> dict[str, object]:
    probe = quick_probe_lidar_repository(path)
    return {
        "mode": "dry_probe",
        "path": str(probe.selection.normalized_path),
        "path_valid": probe.selection.valid,
        "catalog_found": probe.selection.catalog_exists,
        "inspected_top_level_entries": probe.inspected_entries,
        "stopped_by_limit": probe.stopped_by_limit,
        "elapsed_seconds": round(probe.elapsed_seconds, 6),
        "filesystem_note": probe.filesystem_note,
        "recommendation": probe.recommendation,
    }


def real_build(path: Path, max_files: int | None, maximum_duration: float | None) -> dict[str, object]:
    from pyforestscan_qgis.core.lidar_catalog_models import CatalogBuildOptions

    options = CatalogBuildOptions(max_depth=None, max_source_files=max_files)
    start = time.perf_counter()
    result = CatalogJobRunner(
        CatalogJobSpec.create("lidar_catalog_build", path, default_lidar_catalog_path(path), options=options),
        pause_callback=(lambda: maximum_duration is not None and (time.perf_counter() - start) >= maximum_duration),
    ).run()
    elapsed = time.perf_counter() - start
    return {
        "mode": "real_build",
        "path": str(path),
        "maximum_files": max_files,
        "maximum_duration_seconds": maximum_duration,
        "elapsed_seconds": round(elapsed, 3),
        "discovered": result.discovered_count,
        "indexed": result.indexed_count,
        "unchanged": result.unchanged_count,
        "errors": result.error_count,
        "deleted": result.deleted_count,
        "catalog_path": str(result.catalog_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark PyForestScan LiDAR catalog behavior safely.")
    parser.add_argument("--synthetic", action="store_true", help="Run synthetic SQLite/RTree benchmark. Default when no real path is supplied.")
    parser.add_argument("--records", type=int, default=5000, help="Synthetic record count.")
    parser.add_argument("--path", type=Path, help="Real repository path for dry probe or confirmed build.")
    parser.add_argument("--real-dry-probe", action="store_true", help="Probe a real repository without recursive traversal.")
    parser.add_argument("--real-build", action="store_true", help="Run a real catalog build only when --confirm-real-build is also supplied.")
    parser.add_argument("--confirm-real-build", action="store_true", help="Required guard for real catalog builds.")
    parser.add_argument("--max-files", type=int, help="Maximum source files for a controlled real benchmark run.")
    parser.add_argument("--maximum-duration", type=float, help="Maximum duration in seconds for a controlled real benchmark run.")
    args = parser.parse_args()
    if args.real_build:
        if not args.path or not args.confirm_real_build:
            parser.error("--real-build requires --path and --confirm-real-build")
        result = real_build(args.path, args.max_files, args.maximum_duration)
    elif args.path or args.real_dry_probe:
        if not args.path:
            parser.error("--real-dry-probe requires --path")
        result = dry_probe(args.path)
    else:
        result = synthetic_benchmark(args.records)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
