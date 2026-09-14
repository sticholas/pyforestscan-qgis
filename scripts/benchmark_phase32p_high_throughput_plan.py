#!/usr/bin/env python3
"""Compare a frozen polygon plan with Phase 32P component-aware planning."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent
from pyforestscan_qgis.core.work_unit_geometry import NormalizedPolygonGeometry


def _tree_metrics(root: Path) -> dict[str, int]:
    files = directories = bytes_total = 0
    for current, names, filenames in os.walk(root):
        directories += len(names)
        for name in filenames:
            files += 1
            try:
                bytes_total += (Path(current) / name).stat().st_size
            except OSError:
                pass
    return {"files": files, "directories": directories + 1, "bytes": bytes_total}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads((args.legacy_job / "coordinator" / "frozen_execution_plan.json").read_text(encoding="utf-8"))
    source_plan = frozen["source_plan"]
    grid = source_plan["grid"]
    extent = SpatialExtent(**grid["total_extent"])
    polygon = NormalizedPolygonGeometry.from_wkt(frozen["polygon_wkt"], processing_crs=grid["crs"])
    source_path = Path(source_plan["work_units"][0]["source_paths"][0])
    started = time.perf_counter()
    plan = SourceAwareWorkPlanner().plan(
        repository_kind="ept", sources=(NativeSource(source_path, extent, source_type="ept"),),
        polygon_envelope=extent, processing_crs=grid["crs"], product="chm",
        resolution=float(grid["resolution"]), normalized_polygon=polygon,
    )
    planning_seconds = time.perf_counter() - started
    old_candidates = len(source_plan["candidate_work_units"])
    old_required = len(source_plan["work_units"])
    payload = {
        "schema": "phase32p-high-throughput-plan-benchmark-v1",
        "job_id": frozen["job_id"],
        "legacy_plan_signature": frozen["plan_signature"],
        "geometry": {
            "components": len(polygon.parts), "component_areas_m2": polygon.component_areas,
            "total_area_ha": sum(polygon.component_areas) / 10_000.0,
            "envelope_width_m": extent.width, "envelope_height_m": extent.height,
        },
        "legacy": {
            "candidate_objects": old_candidates, "executable_regions": old_required,
            "skipped_objects": old_candidates - old_required, "plan_bytes": (args.legacy_job / "coordinator" / "frozen_execution_plan.json").stat().st_size,
            "tree": _tree_metrics(args.legacy_job),
        },
        "phase32p": {
            "candidate_objects": plan.candidate_count, "executable_regions": plan.required_count,
            "skipped_objects": plan.skipped_count, "components": plan.component_count,
            "clusters": plan.cluster_count, "read_blocks": plan.read_block_count,
            "science_blocks": plan.science_block_count, "checkpoint_tiles": plan.checkpoint_tile_count,
            "outside_polygon_count_estimate": plan.outside_polygon_count_estimate,
            "planning_seconds": planning_seconds, "serialized_plan_bytes": len(json.dumps(plan.to_dict(), sort_keys=True).encode("utf-8")),
            "projected_status_files": plan.checkpoint_tile_count,
            "minimum_core_width_m": min(unit.core_extent.width for unit in plan.work_units),
            "minimum_core_height_m": min(unit.core_extent.height for unit in plan.work_units),
            "maximum_core_width_m": max(unit.core_extent.width for unit in plan.work_units),
            "maximum_core_height_m": max(unit.core_extent.height for unit in plan.work_units),
            "read_amplification": plan.read_amplification,
            "ordinary_regions_use_direct_managed_operation": all(
                unit.read_extent.width <= 2000 and unit.read_extent.height <= 2000 and unit.estimated_memory <= 6 * 1024**3
                for unit in plan.work_units
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
