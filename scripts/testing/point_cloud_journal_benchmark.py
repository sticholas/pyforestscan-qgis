"""Measure journal cursor operations separately from save and visual replay."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from windows_viewer_memory import tree_memory
    original = PointCloudEditSession.load(args.session)
    template = original.operations[0]
    report = {"scope": "Journal cursor and persistence only; not renderer or full export qualification.", "measurements": []}
    for count in (100, 1000, 10000):
        session = PointCloudEditSession(original.source, original.source_crs, original.dimensions,
                                       session_id=original.session_id)
        session._journal = [replace(template, operation_id=str(index)) for index in range(count)]
        session._cursor = count
        undo, redo = [], []
        for _ in range(100):
            start = perf_counter()
            assert session.undo()
            undo.append((perf_counter() - start) * 1000)
            start = perf_counter()
            assert session.redo()
            redo.append((perf_counter() - start) * 1000)
        start = perf_counter()
        path = session.save(args.output_dir / (str(count) + ".json"))
        save_seconds = perf_counter() - start
        memory = tree_memory(os.getpid())
        report["measurements"].append({"edits": count, "journal_bytes": path.stat().st_size,
            "undo_median_ms": statistics.median(undo), "redo_median_ms": statistics.median(redo),
            "save_seconds": save_seconds, "memory_after_save": memory})
    original.source.verify()
    report["original_unchanged"] = True
    atomic_write_json(args.output_dir / "journal_benchmark.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
