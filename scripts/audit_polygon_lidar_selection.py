#!/usr/bin/env python3
"""Audit polygon-to-LiDAR folder selection paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.direct_lidar_selection import DirectLidarFolderSelector, compare_selection_methods
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
from pyforestscan_qgis.core.lidar_catalog_integrity import inspect_catalog_integrity
from pyforestscan_qgis.core.lidar_catalog_query import query_catalog_for_polygon
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.repository_diagnostics import repository_diagnostic_payload
from pyforestscan_qgis.core.types import ProductType


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare direct header scan and catalog polygon LiDAR selection.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--polygon", required=True, help="Polygon WKT")
    parser.add_argument("--polygon-crs", required=True)
    parser.add_argument("--catalog")
    parser.add_argument("--repository-crs")
    parser.add_argument("--recursive", action="store_true", default=True)
    parser.add_argument("--selection-mode", choices=("automatic", "catalog", "direct_header_scan"), default="automatic")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--direct-scan", action="store_true")
    parser.add_argument("--catalog-query", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--verify-headers", action="store_true")
    parser.add_argument("--rebuild-catalog", action="store_true")
    parser.add_argument("--export-report")
    args = parser.parse_args()
    repository = Path(args.repository)
    polygon = normalized_selection_from_wkt(args.polygon, args.polygon_crs)
    catalog = Path(args.catalog) if args.catalog else None
    rebuild_result = None
    if args.rebuild_catalog:
        rebuild_result = build_lidar_catalog(repository, catalog_path=catalog)
        catalog = rebuild_result.catalog_path
    direct = DirectLidarFolderSelector().select(repository, polygon, repository_crs_override=args.repository_crs, recursive=args.recursive)
    catalog_sources = ()
    catalog_status = "not-run"
    catalog_seconds = 0.0
    if catalog is not None and catalog.exists():
        query = query_catalog_for_polygon(catalog, repository, polygon, catalog_crs=args.repository_crs or args.polygon_crs)
        catalog_sources = query.source_records
        catalog_status = query.catalog_integrity_status
        catalog_seconds = query.query_seconds
    comparison = compare_selection_methods(direct, catalog_sources, catalog_seconds=catalog_seconds)
    preflight = run_polygon_batch_preflight(
        PolygonBatchRequest(
            repository,
            repository / "audit_output",
            polygon,
            (ProductType.CHM,),
            BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0),
            catalog_path=catalog,
            selection_mode=args.selection_mode,
            repository_crs_override=args.repository_crs,
        ),
        backend_probe=lambda: (True, "audit only"),
    )
    payload = {
        "repository": str(repository),
        "catalog": str(catalog) if catalog else None,
        "catalog_rebuild": None if rebuild_result is None else {
            "catalog_path": str(rebuild_result.catalog_path),
            "discovered_count": rebuild_result.discovered_count,
            "indexed_count": rebuild_result.indexed_count,
            "error_count": rebuild_result.error_count,
            "cancelled": rebuild_result.cancelled,
        },
        "catalog_health": None if catalog is None or not catalog.exists() else inspect_catalog_integrity(catalog, repository).status,
        "direct": {
            "discovered_file_count": direct.discovered_file_count,
            "metadata_read_count": direct.metadata_read_count,
            "usable_source_count": direct.usable_source_count,
            "intersecting_source_count": direct.intersecting_source_count,
            "intersecting_source_paths": [str(path) for path in direct.intersecting_source_paths],
            "blockers": list(direct.blockers),
            "warnings": list(direct.warnings),
        },
        "catalog_selection": {
            "status": catalog_status,
            "intersecting_source_paths": [str(source.path) for source in catalog_sources],
        },
        "comparison": {
            "summary": comparison.discrepancy_summary,
            "direct_only": [str(path) for path in comparison.selected_by_direct_only],
            "catalog_only": [str(path) for path in comparison.selected_by_catalog_only],
            "catalog_selection_failure": comparison.catalog_selection_failure,
        },
        "preflight": {
            "ready": preflight.ready,
            "selection_method": preflight.selection_method,
            "selected_sources": [str(source.path) for source in preflight.selected_sources],
            "blockers": list(preflight.blockers),
            "warnings": list(preflight.warnings),
            "plan_signature": preflight.plan_signature,
        },
    }
    if catalog is not None and catalog.exists():
        payload["diagnostics"] = repository_diagnostic_payload(repository, catalog, sample_limit=args.sample_size)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.export_report:
        Path(args.export_report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
