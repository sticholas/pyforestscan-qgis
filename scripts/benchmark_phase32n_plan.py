#!/usr/bin/env python3
"""Benchmark EPT hierarchy rejection and spatial ordering for a frozen plan."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _intersects(extent: dict, box: tuple[float, float, float, float]) -> bool:
    return not (extent["xmax"] <= box[0] or extent["xmin"] >= box[2] or extent["ymax"] <= box[1] or extent["ymin"] >= box[3])


def _travel(points: list[tuple[float, float, str]]) -> float:
    return sum(math.hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1]) for index in range(1, len(points)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ept-json", type=Path, required=True)
    parser.add_argument("--hierarchy-json", type=Path, required=True)
    parser.add_argument("--frozen-plan", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.ept_json.read_text(encoding="utf-8"))
    hierarchy = json.loads(args.hierarchy_json.read_text(encoding="utf-8"))
    source_plan = json.loads(args.frozen_plan.read_text(encoding="utf-8"))["source_plan"]
    bounds = metadata["bounds"]
    side = max(bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2])
    cells = {(x, y) for key in hierarchy for depth, x, y, _z in (map(int, key.split("-")),) if depth == args.depth}
    width = side / (2 ** args.depth)
    boxes = [(bounds[0] + x * width, bounds[1] + y * width, bounds[0] + (x + 1) * width, bounds[1] + (y + 1) * width) for x, y in cells]
    candidates = source_plan["candidate_work_units"]
    hierarchy_candidates = sum(any(_intersects(unit["core_extent"], box) for box in boxes) for unit in candidates)
    centers = [((unit["core_extent"]["xmin"] + unit["core_extent"]["xmax"]) / 2, (unit["core_extent"]["ymin"] + unit["core_extent"]["ymax"]) / 2, unit["work_unit_id"]) for unit in source_plan["work_units"]]
    def morton(point: tuple[float, float, str]) -> int:
        x = int((point[0] - bounds[0]) / side * 65535); y = int((point[1] - bounds[1]) / side * 65535); value = 0
        for bit in range(16):
            value |= ((x >> bit) & 1) << (2 * bit); value |= ((y >> bit) & 1) << (2 * bit + 1)
        return value
    row_travel = _travel(centers); morton_travel = _travel(sorted(centers, key=morton))
    payload = {
        "schema": "phase32n-plan-benchmark-v1", "root_hierarchy_records": len(hierarchy),
        "hierarchy_depth": args.depth, "occupied_xy_cells": len(cells), "cell_width": width,
        "envelope_candidates": len(candidates), "hierarchy_candidates": hierarchy_candidates,
        "hierarchy_pruned": len(candidates) - hierarchy_candidates,
        "polygon_required": len(source_plan["work_units"]), "row_major_travel": row_travel,
        "morton_travel": morton_travel, "travel_reduction_percent": (1 - morton_travel / row_travel) * 100,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
