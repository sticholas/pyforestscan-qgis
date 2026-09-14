"""Windows-safe diagnostic collision canary using the production writer."""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyforestscan_qgis.core.tile_diagnostics import write_stage_record


STAGES = ("REQUEST", "EPT_READ_STARTED", "EPT_READ_COMPLETED", "POLYGON_CLIP_STARTED", "POLYGON_CLIP_COMPLETED", "HEIGHT_PREPARATION_COMPLETED", "VOXEL_STAT_STARTED", "VOXEL_STAT_INPUT_VALIDATED", "VOXEL_STAT_COMPLETED", "TILE_RASTER_WRITTEN", "TILE_VALIDATED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd() / "diagnostic_collision_canary")
    args = parser.parse_args()
    target = args.root / "work_units" / "voxel_stat" / "wu-canary" / "diagnostics" / "tile_diagnostics.json"
    for index, stage in enumerate(STAGES):
        write_stage_record(target, stage=stage, payload={"attempt": 1, "index": index})
    for attempt in range(2, 4):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda index: write_stage_record(target, stage=f"RETRY_{attempt}_{index}", payload={"attempt": attempt, "index": index}), range(4)))
    print(target)
    print(target.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
