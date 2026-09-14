#!/usr/bin/env python3
"""Summarize durable Phase 32Q parent and bounded-subread timing evidence."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(len(values) - 1, lower + 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def distribution(values) -> dict[str, float | int]:
    numbers = [float(value) for value in values if value is not None]
    return {
        "count": len(numbers),
        "sum": sum(numbers),
        "mean": statistics.mean(numbers) if numbers else 0.0,
        "p50": percentile(numbers, 0.50),
        "p75": percentile(numbers, 0.75),
        "p90": percentile(numbers, 0.90),
        "p95": percentile(numbers, 0.95),
        "maximum": max(numbers, default=0.0),
    }


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def summarize(root: Path) -> dict:
    parents = [load_json(path) for path in root.glob("work_units/wu-*/diagnostics/work_unit_timing.json")]
    subreads = [load_json(path) for path in root.glob("work_units/wu-*/bounded_subreads/*/diagnostics/science_timing.json")]
    checkpoints = [load_json(path) for path in root.glob("work_units/wu-*/status.json")]
    outputs = [path for path in root.glob("work_units/wu-*/outputs/chm_core.tif") if path.is_file()]
    terminal = load_json(root / "coordinator/terminal_result.json")
    progress = load_json(root / "coordinator/progress_snapshot.json")
    elapsed = float(terminal.get("elapsed_seconds") or progress.get("elapsed_seconds") or 0)
    parent_total = sum(float(item.get("total_seconds", 0) or 0) for item in parents)
    return {
        "root": str(root),
        "terminal_state": terminal.get("state"),
        "wall_seconds": elapsed,
        "parent_regions": len(parents),
        "bounded_subreads": len(subreads),
        "parent_total_seconds": distribution(item.get("total_seconds") for item in parents),
        "parent_science_seconds": distribution(item.get("bounded_read_and_chm_seconds") for item in parents),
        "core_extraction_seconds": distribution(item.get("chm_core_extraction_seconds") for item in parents),
        "checkpoint_seconds": distribution(item.get("chm_checksum_and_checkpoint_seconds") for item in parents),
        "subread_total_seconds": distribution(item.get("total_seconds") for item in subreads),
        "ept_read_seconds": distribution(item.get("ept_read_and_point_decode_seconds") for item in subreads),
        "hag_seconds": distribution(item.get("hag_contract_seconds") for item in subreads),
        "pyforestscan_seconds": distribution(item.get("pyforestscan_chm_seconds") for item in subreads),
        "raster_write_seconds": distribution(item.get("buffered_raster_write_seconds") for item in subreads),
        "points": distribution(item.get("point_count") for item in subreads),
        "worker_peak_rss": distribution(item.get("worker_peak_rss") for item in parents),
        "output_size_bytes": distribution(path.stat().st_size for path in outputs),
        "checkpoint_statuses": {status: sum(item.get("status") == status for item in checkpoints) for status in sorted({item.get("status") for item in checkpoints if item.get("status")})},
        "known_parent_time": parent_total,
        "unaccounted_wall_time": max(0.0, elapsed - parent_total),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Path to the ept-full durable run directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = summarize(args.root)
    text = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
