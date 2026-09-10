"""Read-only real-PDAL qualification for authoritative selection resizing."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--center", nargs=2, type=float, required=True, metavar=("X", "Y"))
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--distance", type=float, required=True)
    parser.add_argument("--height-range", nargs=2, type=float, metavar=("MIN", "MAX"))
    parser.add_argument("--height-axis", choices=("Z", "HeightAboveGround"), default="Z")
    args = parser.parse_args()
    if args.radius <= 0 or args.radius + args.distance <= 0:
        parser.error("Original and resized radii must be positive.")

    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.selection import (
        SelectionDefinition, SelectionResolver, circular_selection, resized_selection)
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity

    source = SourceIdentity.capture(args.source)
    report = {"source": asdict(source), "passed": False}
    try:
        reader = {"type": "readers.copc" if source.source_type == "COPC" else "readers.las",
                  "filename": source.path}
        pipeline = pdal.Pipeline(json.dumps([reader]))
        pipeline.execute()
        points = pipeline.arrays[0]
        if not 0 < len(points) <= 3_000_000:
            raise ValueError("Independent full-source qualification is limited to three million points.")
        quick = next(iter(pdal.Pipeline(json.dumps([reader])).quickinfo.values()))
        srs = quick.get("srs", {})
        crs = srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:" + source.sha256
        cx, cy = args.center
        base = SelectionDefinition("resize-base", "qualification", source.sha256,
            source.source_type, ((cx-args.radius, cy-args.radius),
            (cx+args.radius, cy-args.radius), (cx+args.radius, cy+args.radius),
            (cx-args.radius, cy+args.radius), (cx-args.radius, cy-args.radius)), crs)
        definition = circular_selection(base, center=args.center, radius=args.radius)
        if args.height_range:
            key = "hag_filter" if args.height_axis == "HeightAboveGround" else "z_filter"
            definition = replace(definition, **{key: tuple(args.height_range)})
        resized = resized_selection([definition], args.distance, selection_id="resized")[0]
        resolver = SelectionResolver(source)
        started = time.monotonic()
        original_result = resolver.resolve([definition])
        resized_result = resolver.resolve([resized])
        elapsed = time.monotonic() - started

        def independent(radius):
            mask = (points["X"]-cx) ** 2 + (points["Y"]-cy) ** 2 <= radius ** 2
            if args.height_range:
                if args.height_axis not in (points.dtype.names or ()):
                    raise ValueError(f"Source does not contain {args.height_axis}.")
                low, high = args.height_range
                mask &= ((points[args.height_axis] >= low) &
                         (points[args.height_axis] <= high))
            codes, counts = np.unique(points["Classification"][mask], return_counts=True)
            return int(mask.sum()), tuple((int(c), int(n)) for c, n in zip(codes, counts))

        original_expected = independent(args.radius)
        resized_expected = independent(args.radius + args.distance)
        source.verify()
        report.update({
            "shape": "circle",
            "center": args.center,
            "original_radius": args.radius,
            "distance": args.distance,
            "resized_radius": args.radius + args.distance,
            "height_range": args.height_range,
            "height_axis": args.height_axis if args.height_range else None,
            "original_result": asdict(original_result),
            "resized_result": asdict(resized_result),
            "original_expected_count": original_expected[0],
            "resized_expected_count": resized_expected[0],
            "elapsed_seconds": elapsed,
            "source_unchanged": True,
        })
        report["passed"] = (
            original_result.resolved_point_count == original_expected[0]
            and original_result.classification_counts == original_expected[1]
            and resized_result.resolved_point_count == resized_expected[0]
            and resized_result.classification_counts == resized_expected[1]
            and resized_result.resolved_point_count > original_result.resolved_point_count)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
