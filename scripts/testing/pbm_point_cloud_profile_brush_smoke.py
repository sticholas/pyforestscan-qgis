"""Read-only real-PDAL qualification for authoritative Profile Brush selection."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def coordinate_pairs(values, label):
    if len(values) < 4 or len(values) % 2:
        raise ValueError(f"{label} requires at least two X/Y coordinate pairs.")
    return tuple((values[index], values[index + 1])
                 for index in range(0, len(values), 2))


def round_brush_mask(x, y, path, radius, np):
    selected = np.zeros(len(x), dtype=bool)
    radius_squared = radius * radius
    if len(path) == 1:
        return (x - path[0][0])**2 + (y - path[0][1])**2 <= radius_squared
    for first, second in zip(path, path[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length_squared = dx * dx + dy * dy
        fraction = np.clip(
            ((x - first[0]) * dx + (y - first[1]) * dy) / length_squared,
            0, 1)
        nearest_x = first[0] + fraction * dx
        nearest_y = first[1] + fraction * dy
        selected |= ((x - nearest_x)**2 + (y - nearest_y)**2
                     <= radius_squared)
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-path", nargs="+", type=float, required=True,
                        metavar="XY")
    parser.add_argument("--thickness", type=float, required=True)
    parser.add_argument("--brush-path", nargs="+", type=float, required=True,
                        metavar="DISTANCE_HEIGHT")
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--axis", choices=("Z", "HeightAboveGround"), default="Z")
    args = parser.parse_args()

    profile_path = coordinate_pairs(args.profile_path, "Profile path")
    brush_path = coordinate_pairs(args.brush_path, "Brush path")
    if args.thickness <= 0 or args.radius <= 0:
        parser.error("Thickness and radius must be positive.")

    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = (os.add_dll_directory(str(dll))
                  if os.name == "nt" and dll.is_dir() else None)
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.profile import (
        profile_coordinates, profile_membership)
    from pyforestscan_qgis.core.point_cloud.selection import (
        SelectionDefinition, SelectionResolver)
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry

    source = SourceIdentity.capture(args.source)
    report = {"source": asdict(source), "passed": False}
    try:
        reader = {
            "type": "readers.copc" if source.source_type == "COPC" else "readers.las",
            "filename": source.path,
        }
        pipeline = pdal.Pipeline(json.dumps([reader]))
        pipeline.execute()
        points = pipeline.arrays[0]
        if not 0 < len(points) <= 3_000_000:
            raise ValueError(
                "Independent full-source qualification is limited to three million points.")
        if args.axis not in (points.dtype.names or ()):
            raise ValueError(f"Source does not contain {args.axis}.")
        quick = next(iter(pdal.Pipeline(json.dumps([reader])).quickinfo.values()))
        srs = quick.get("srs", {})
        crs = (srs.get("compoundwkt") or srs.get("wkt")
               or "SOURCE_LOCAL:" + source.sha256)
        profile = SliceGeometry(
            profile_path[0], profile_path[-1], args.thickness, crs, args.axis,
            path=profile_path)
        definition = SelectionDefinition(
            "profile-brush", "qualification", source.sha256, source.source_type,
            profile.corridor(), crs, profile_a=profile.a, profile_b=profile.b,
            profile_path=profile.points, profile_thickness=profile.thickness,
            profile_axis=args.axis, depth_mode="SLICE_CORRIDOR",
            profile_brush_path=brush_path, profile_brush_radius=args.radius)

        started = time.monotonic()
        result = SelectionResolver(source).resolve([definition])
        elapsed = time.monotonic() - started

        along, _cross, _distance = profile_coordinates(
            profile, points["X"], points["Y"], np)
        mask = profile_membership(profile, points["X"], points["Y"], np)
        mask &= round_brush_mask(
            along, points[args.axis], brush_path, args.radius, np)
        expected = int(mask.sum())
        codes, counts = np.unique(points["Classification"][mask], return_counts=True)
        expected_classes = tuple(
            (int(code), int(count)) for code, count in zip(codes, counts))
        source.verify()
        report.update({
            "profile_path": profile_path,
            "profile_length": profile.length,
            "thickness": args.thickness,
            "brush_path": brush_path,
            "radius": args.radius,
            "axis": args.axis,
            "result": asdict(result),
            "expected_count": expected,
            "expected_classification_counts": expected_classes,
            "elapsed_seconds": elapsed,
            "source_unchanged": True,
        })
        report["passed"] = (
            expected > 0
            and result.resolved_point_count == expected
            and result.classification_counts == expected_classes)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if dll_handle is not None:
            dll_handle.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
