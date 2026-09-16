"""Replay one bounded work unit for forensic diagnostics.

This developer command intentionally does not invoke the planner or the full
polygon batch.  It reads exactly the supplied bounds and emits metadata-only
counts, making it safe to investigate a single remote EPT tile.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one PyForestScan work unit")
    parser.add_argument("--source", required=True)
    parser.add_argument("--work-unit-id", required=True)
    parser.add_argument("--xmin", type=float, required=True)
    parser.add_argument("--ymin", type=float, required=True)
    parser.add_argument("--xmax", type=float, required=True)
    parser.add_argument("--ymax", type=float, required=True)
    parser.add_argument("--crs", required=True)
    parser.add_argument("--product", default="voxel_stat")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        from pyforestscan.handlers import read_lidar
        from pyforestscan_qgis.core.tile_diagnostics import point_array_summary
    except Exception as exc:  # pragma: no cover - depends on managed runtime
        parser.error(f"PyForestScan runtime unavailable: {exc}")
    bounds = ((args.xmin, args.xmax), (args.ymin, args.ymax))
    arrays = read_lidar(args.source, args.crs, bounds=bounds, hag=False)
    if isinstance(arrays, (list, tuple)):
        import numpy as np
        points = np.concatenate(tuple(arrays)) if arrays else np.empty(0)
    else:
        points = arrays
    payload = {
        "schema": "pyforestscan-work-unit-replay-v1",
        "work_unit_id": args.work_unit_id,
        "source": args.source,
        "product": args.product,
        "bounds": bounds,
        "crs": args.crs,
        "classification": "SOURCE_READ",
        "source_read": point_array_summary(points),
        "after_polygon_clip": None,
        "after_height_preparation": None,
        "before_chm": None,
        "before_voxel": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

