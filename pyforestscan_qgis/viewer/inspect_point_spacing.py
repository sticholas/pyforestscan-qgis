"""Bounded managed-runtime horizontal point-spacing inspection."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.atomic_state import atomic_write_json


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
        # Read small spatial windows at native resolution. Decimating before a
        # nearest-neighbor calculation would falsely increase apparent spacing.
        bounds = quick.get("bounds") or {}
        xmin, ymin = float(bounds["minx"]), float(bounds["miny"])
        xmax, ymax = float(bounds["maxx"]), float(bounds["maxy"])
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("The source has invalid horizontal bounds.")
        samples = []
        window_fraction = 1 / 15
        window_limit = 10000
        for x_factor in (.2, .5, .8):
            for y_factor in (.2, .5, .8):
                cancelled()
                x_center = xmin + (xmax - xmin) * x_factor
                y_center = ymin + (ymax - ymin) * y_factor
                half_x = (xmax - xmin) * window_fraction / 2
                half_y = (ymax - ymin) * window_fraction / 2
                crop_bounds = f"([{x_center-half_x},{x_center+half_x}], [{y_center-half_y},{y_center+half_y}])"
                pipeline = pdal.Pipeline(json.dumps({"pipeline": [
                    {"type": "readers.las", "filename": str(source)},
                    {"type": "filters.crop", "bounds": crop_bounds},
                    {"type": "filters.head", "count": window_limit},
                ]}))
                pipeline.execute()
                arrays = tuple(pipeline.arrays or ())
                if arrays and sum(len(array) for array in arrays):
                    samples.append(np.concatenate(arrays))
        if not samples:
            raise ValueError("Could not obtain a usable full-resolution spacing sample.")
        points = np.concatenate(samples)
        if len(points) < 2:
            raise ValueError("Could not obtain a usable point-spacing sample.")
        cancelled()
        coordinates = np.column_stack((points["X"], points["Y"]))
        distances, _ = cKDTree(coordinates).query(coordinates, k=2, workers=-1)
        nearest = distances[:, 1]
        nearest = nearest[np.isfinite(nearest) & (nearest > 0)]
        if len(nearest) < 2:
            raise ValueError("The sampled points do not provide a valid horizontal-spacing distribution.")
        median = float(np.median(nearest))
        p10, p90 = (float(value) for value in np.percentile(nearest, (10, 90)))
        result = {
            "status": "COMPLETE", "point_count": count, "sample_count": len(points),
            "windows_sampled": len(samples), "p10_spacing": round(p10, 6),
            "median_spacing": round(median, 6), "p90_spacing": round(p90, 6),
            "method": "horizontal nearest-neighbor spacing from bounded full-resolution spatial windows",
        }
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
