#!/usr/bin/env python3
"""Summarize durable polygon work-unit timing evidence without QGIS."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _percentile(values: list[float], fraction: float) -> float:
    return values[min(len(values) - 1, max(0, int((len(values) - 1) * fraction)))]


def summarize(run_folder: Path) -> dict[str, object]:
    rows = []
    for path in sorted((run_folder / "work_units").glob("wu-*/diagnostics/work_unit_timing.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
    metrics: dict[str, object] = {}
    keys = sorted({key for row in rows for key, value in row.items() if isinstance(value, (int, float)) and not isinstance(value, bool)})
    for key in keys:
        values = sorted(float(row[key]) for row in rows if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool))
        if values:
            metrics[key] = {
                "count": len(values), "median": statistics.median(values),
                "p75": _percentile(values, 0.75), "p90": _percentile(values, 0.90),
                "maximum": max(values), "sum": sum(values),
            }
    return {"schema": "pyforestscan-work-unit-timing-summary-v1", "run_folder": str(run_folder), "work_units_with_timing": len(rows), "metrics": metrics}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-folder", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = summarize(args.run_folder)
    text = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
