#!/usr/bin/env python3
"""Reproducible synthetic benchmark for adaptive planning decisions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.processing_performance import measure_plan
from pyforestscan_qgis.core.source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent

SCENARIOS = (
    ("small", 200.0, 200.0),
    ("medium", 2000.0, 1500.0),
    ("large", 10000.0, 7000.0),
    ("very_large", 30000.0, 20000.0),
)

def benchmark(repository_kind="ept", network=False, memory_gib=8, cpus=8):
    rows = []
    source_type = "laz" if repository_kind == "folder" else repository_kind
    prefix = "//network/" if network else "/local/"
    for name, width, height in SCENARIOS:
        extent = SpatialExtent(0, 0, width, height)
        sources = (NativeSource(Path(prefix + ("tile.laz" if repository_kind == "folder" else "ept.json")), extent, source_type=source_type),)
        _plan, summary = measure_plan(
            SourceAwareWorkPlanner(), repository_kind=repository_kind, sources=sources,
            polygon_envelope=extent, processing_crs="EPSG:26904", product="chm",
            resolution=1.0, available_memory_bytes=memory_gib * 1024**3, cpu_count=cpus,
        )
        row = summary.to_dict(); row["scenario"] = name; row["repository_kind"] = repository_kind; row["network"] = network
        rows.append(row)
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-kind", choices=("ept", "copc", "folder"), default="ept")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--memory-gib", type=int, default=8)
    parser.add_argument("--cpus", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = benchmark(args.repository_kind, args.network, args.memory_gib, args.cpus)
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print("scenario\tpath\tunits\tworkers\tplan_ms\tread_amp\tpeak_mib")
    for row in rows:
        print(f"{row['scenario']}\t{row['execution_path']}\t{row['required_units']}\t{row['concurrency']}\t{row['planning_seconds']*1000:.3f}\t{row['read_amplification']:.3f}\t{row['estimated_peak_memory']/1024**2:.1f}")

if __name__ == "__main__":
    main()
