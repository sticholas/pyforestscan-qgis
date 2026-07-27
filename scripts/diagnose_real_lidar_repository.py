#!/usr/bin/env python3
"""Inspect a real LiDAR repository catalog without QGIS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.lidar_catalog_integrity import inspect_catalog_integrity, inspect_catalog_records, repair_catalog
from pyforestscan_qgis.core.lidar_repository_discovery import discover_lidar_repository
from pyforestscan_qgis.core.repository_diagnostics import repository_diagnostic_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose PyForestScan LiDAR repository catalog state.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--pbm-python")
    parser.add_argument("--polygon-bounds", nargs=4, type=float)
    parser.add_argument("--polygon-crs")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--verify-sample", action="store_true")
    parser.add_argument("--verify-all", action="store_true")
    parser.add_argument("--repair-rtree", action="store_true")
    parser.add_argument("--full-rebuild", action="store_true")
    args = parser.parse_args()
    repository = Path(args.repository)
    catalog = Path(args.catalog)
    if args.repair_rtree:
        report = repair_catalog(catalog, repository)
        print(report.message)
        print("Before:", report.before.status)
        print("After:", report.after.status)
        return 0
    discovery = discover_lidar_repository(repository)
    integrity = inspect_catalog_integrity(catalog, repository)
    records = inspect_catalog_records(catalog, repository, sample_size=args.sample_size)
    payload = repository_diagnostic_payload(repository, catalog, sample_limit=args.sample_size)
    payload["record_inspection"] = {
        "first_paths": [str(path) for path in records.first_paths],
        "last_paths": [str(path) for path in records.last_paths],
        "sample_paths": [str(path) for path in records.sample_paths],
        "extent_defining_sources": [dict(item.__dict__, source_path=str(item.source_path)) for item in records.extent_defining_sources],
    }
    payload["likely_diagnosis"] = _diagnosis(integrity)
    payload["recommended_action"] = _recommendation(integrity)
    payload["discovered_files"] = discovery.supported_files_found
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def _diagnosis(report) -> str:
    if report.status == "CRS Assignment Required":
        return "Sources have usable bounds but no effective coordinate system; overlap with polygon cannot be trusted yet."
    if report.status == "Healthy with validated repository CRS override":
        return "Repository CRS override is active; compare extents and candidate results."
    return report.status


def _recommendation(report) -> str:
    if report.status == "CRS Assignment Required":
        return "Inspect headers, then assign a repository coordinate system if the files genuinely lack embedded CRS."
    if report.status == "Needs Repair":
        return "Repair Spatial Index or Refresh File Metadata."
    return "No catalog repair required."


if __name__ == "__main__":
    raise SystemExit(main())
