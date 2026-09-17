"""Bounded managed-runtime horizontal point-spacing inspection."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.atomic_state import atomic_write_json

SCHEMA_VERSION = 1
SAMPLE_WINDOWS = 9
WINDOW_LIMIT = 10000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--cancel-file", type=Path)
    args = parser.parse_args()

    def cancelled():
        if args.cancel_file and args.cancel_file.exists():
            raise InterruptedError("Point-spacing inspection cancelled.")

    source = args.source.resolve(strict=True)
    if source.suffix.lower() not in (".las", ".laz"):
        raise ValueError("Point-spacing inspection needs a local LAS or LAZ source.")
    source_stat = source.stat()
    report_json = source.with_name(source.stem + ".pyforestscan.spacing.json")
    report_markdown = source.with_name(source.stem + ".pyforestscan.spacing.md")
    try:
        existing = json.loads(report_json.read_text(encoding="utf-8"))
        identity = existing.get("source_identity", {})
        if (existing.get("schema_version") == SCHEMA_VERSION
                and identity.get("size") == source_stat.st_size
                and identity.get("modified_ns") == source_stat.st_mtime_ns):
            reused = dict(existing)
            reused["reused"] = True
            atomic_write_json(args.result, reused)
            print(json.dumps(reused, sort_keys=True), flush=True)
            return
    except (OSError, ValueError):
        pass

    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    try:
        import numpy as np
        import pdal
        from scipy.spatial import cKDTree
        cancelled()
        quick = next(iter(pdal.Pipeline(json.dumps({
            "pipeline": [{"type": "readers.las", "filename": str(source)}]
        })).quickinfo.values()))
        count = int(quick.get("num_points", 0))
        if count < 2:
            raise ValueError("Point-spacing inspection needs at least two points.")
        window_count = min(SAMPLE_WINDOWS, max(1, math.ceil(count / 2)))
        width = min(WINDOW_LIMIT, max(2, count // window_count))
        starts = tuple(
            min(max(0, count - width), round((count - width) * index / max(1, window_count - 1)))
            for index in range(window_count)
        )

        def inspect_block(start):
            cancelled()
            pipeline = pdal.Pipeline(json.dumps({"pipeline": [{
                "type": "readers.las", "filename": str(source), "start": int(start), "count": int(width),
            }]}))
            pipeline.execute()
            arrays = tuple(pipeline.arrays or ())
            points = np.concatenate(arrays) if arrays else np.empty(0)
            if len(points) < 2:
                return np.empty(0)
            coordinates = np.column_stack((points["X"], points["Y"]))
            distances, _ = cKDTree(coordinates).query(coordinates, k=2, workers=-1)
            return distances[:, 1]

        # Three bounded I/O jobs improve latency without overwhelming a shared drive
        # or competing with the QGIS viewer for memory.
        nearest_blocks = []
        with ThreadPoolExecutor(max_workers=min(3, len(starts))) as pool:
            futures = {pool.submit(inspect_block, start): start for start in starts}
            for future in as_completed(futures):
                cancelled()
                values = future.result()
                values = values[np.isfinite(values) & (values > 0)]
                if len(values):
                    nearest_blocks.append(values)
        if not nearest_blocks:
            raise ValueError("The sampled source blocks do not provide valid horizontal spacing.")
        nearest = np.concatenate(nearest_blocks)
        median = float(np.median(nearest))
        p10, p90 = (float(value) for value in np.percentile(nearest, (10, 90)))
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "COMPLETE",
            "source": str(source),
            "source_identity": {"size": source_stat.st_size, "modified_ns": source_stat.st_mtime_ns},
            "point_count": count,
            "sample_count": int(sum(len(values) for values in nearest_blocks)),
            "windows_requested": window_count,
            "windows_sampled": len(nearest_blocks),
            "points_per_window_limit": width,
            "p10_spacing": round(p10, 6),
            "median_spacing": round(median, 6),
            "p90_spacing": round(p90, 6),
            "method": "horizontal nearest-neighbor spacing from bounded native-resolution source blocks",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_json": str(report_json),
            "report_markdown": str(report_markdown),
            "reused": False,
        }
        atomic_write_json(report_json, result)
        report_markdown.write_text(
            "# PyForestScan Point Spacing Report\n\n"
            f"Source: {source}\n\n"
            f"- Source points: {count:,}\n"
            f"- Native-resolution source blocks sampled: {len(nearest_blocks)} of {window_count}\n"
            f"- Nearest-neighbor spacing (10th / median / 90th): "
            f"{p10:.6f} / {median:.6f} / {p90:.6f} source units\n"
            f"- Method: {result['method']}\n"
            f"- Generated: {result['generated_at']}\n",
            encoding="utf-8")
        atomic_write_json(args.result, result)
        print(json.dumps(result, sort_keys=True), flush=True)
    finally:
        if dll_handle:
            dll_handle.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
