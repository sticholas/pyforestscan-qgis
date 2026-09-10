"""Read-only real-PDAL selection qualification; run in managed science Python."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--sphere-center", nargs=3, type=float)
    parser.add_argument("--sphere-radius", type=float)
    parser.add_argument("--sphere-axis", choices=("Z", "HeightAboveGround"), default="Z")
    parser.add_argument("--box-bounds", nargs=4, type=float,
                        metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    parser.add_argument("--height-range", nargs=2, type=float, metavar=("MIN", "MAX"))
    parser.add_argument("--height-axis", choices=("Z", "HeightAboveGround"), default="Z")
    parser.add_argument("--invert", action="store_true")
    args = parser.parse_args()
    sphere = args.sphere_center is not None or args.sphere_radius is not None
    box = args.box_bounds is not None or args.height_range is not None
    if ((args.sphere_center is None) != (args.sphere_radius is None)
            or (args.box_bounds is None) != (args.height_range is None)
            or sum((bool(args.large), sphere, box)) > 1):
        parser.error("Choose one complete large, sphere, or box qualification.")
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.selection import (
        SelectionDefinition, SelectionResolver, reader_spec, spherical_selection)
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity

    source = SourceIdentity.capture(args.source)
    report = {"source": asdict(source), "passed": False, "large": args.large}
    try:
        kind = "readers.copc" if source.source_type == "COPC" else "readers.las"
        read = {"type": kind, "filename": source.path}
        meta = next(iter(pdal.Pipeline(json.dumps([read])).quickinfo.values()))
        srs = meta.get("srs", {})
        crs = srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:" + source.sha256
        bounds = meta["bounds"]
        xmin, ymin = bounds["minx"], bounds["miny"]
        xmax, ymax = bounds["maxx"], bounds["maxy"]
        if args.sphere_center:
            if not 0 < meta["num_points"] <= 3_000_000:
                raise ValueError("Full-reference sphere test is limited to three million points.")
            x, y, _height = args.sphere_center
            width = args.sphere_radius
        elif args.box_bounds:
            if not 0 < meta["num_points"] <= 3_000_000:
                raise ValueError("Full-reference box test is limited to three million points.")
            xmin_box, ymin_box, xmax_box, ymax_box = args.box_bounds
            if xmin_box >= xmax_box or ymin_box >= ymax_box:
                raise ValueError("Box bounds must have positive width and height.")
            x, y, width = xmin_box, ymin_box, xmax_box-xmin_box
        elif args.large:
            if source.source_type != "COPC":
                raise ValueError("Large qualification must use indexed COPC.")
            x, y = (xmin + xmax) / 2, (ymin + ymax) / 2
            width = min(10, (xmax - xmin) / 4, (ymax - ymin) / 4)
        else:
            if not 0 < meta["num_points"] <= 2_000_000:
                raise ValueError("Full-reference test is limited to small fixtures.")
            x, y = xmin, ymin
            width = min(xmax - xmin, ymax - ymin) * .55
        ring = (((xmin_box,ymin_box),(xmax_box,ymin_box),(xmax_box,ymax_box),
                 (xmin_box,ymax_box),(xmin_box,ymin_box)) if args.box_bounds else
                ((x, y), (x + width, y), (x, y + width), (x, y)))
        definition = SelectionDefinition("triangle", "qualification", source.sha256,
                                         source.source_type, ring, crs)
        if args.sphere_center:
            definition = spherical_selection(definition, center=args.sphere_center,
                                             radius=args.sphere_radius, axis=args.sphere_axis)
        elif args.box_bounds:
            key = "hag_filter" if args.height_axis == "HeightAboveGround" else "z_filter"
            definition = replace(definition, **{key: tuple(args.height_range),
                "depth_mode": "CUSTOM_DEPTH_RANGE"})
        if args.invert:
            definition = replace(definition, invert_result=True)
        resolver = SelectionResolver(source)
        result = resolver.resolve([definition])
        report["result"] = asdict(result)
        report["reader"] = reader_spec(source, [definition])
        if args.sphere_center:
            reference = pdal.Pipeline(json.dumps([read]))
            reference.execute()
            points = reference.arrays[0]
            if args.sphere_axis not in (points.dtype.names or ()):
                raise ValueError(f"Source does not contain {args.sphere_axis}.")
            cx, cy, cz = args.sphere_center
            mask = (((points["X"]-cx)/args.sphere_radius)**2 +
                    ((points["Y"]-cy)/args.sphere_radius)**2 +
                    ((points[args.sphere_axis]-cz)/args.sphere_radius)**2 <= 1)
            if args.invert:
                mask = ~mask
            expected = int(mask.sum())
            codes, counts = np.unique(points["Classification"][mask], return_counts=True)
            report["classification_reference_passed"] = result.classification_counts == tuple(
                (int(c), int(n)) for c, n in zip(codes, counts))
            report["reference_kind"] = f"all original points, independent source-{args.sphere_axis} sphere"
            report["sphere"] = {"center": args.sphere_center, "radius": args.sphere_radius,
                                "axis": args.sphere_axis}
        elif args.box_bounds:
            reference = pdal.Pipeline(json.dumps([read]))
            reference.execute()
            points = reference.arrays[0]
            if args.height_axis not in (points.dtype.names or ()):
                raise ValueError(f"Source does not contain {args.height_axis}.")
            xmin_box, ymin_box, xmax_box, ymax_box = args.box_bounds
            low, high = args.height_range
            mask = ((points["X"] >= xmin_box) & (points["X"] <= xmax_box) &
                    (points["Y"] >= ymin_box) & (points["Y"] <= ymax_box) &
                    (points[args.height_axis] >= low) & (points[args.height_axis] <= high))
            if args.invert:
                mask = ~mask
            expected = int(mask.sum())
            codes, counts = np.unique(points["Classification"][mask], return_counts=True)
            report["classification_reference_passed"] = result.classification_counts == tuple(
                (int(c), int(n)) for c, n in zip(codes, counts))
            report["reference_kind"] = f"all original points, independent XY/{args.height_axis} box"
            report["box"] = {"bounds": args.box_bounds, "height_range": args.height_range,
                             "height_axis": args.height_axis}
        elif args.large:
            # Independently resolve with PDAL's own crop stage, not a display LOD.
            wkt = "POLYGON ((" + ", ".join(f"{px} {py}" for px, py in ring) + "))"
            reference = pdal.Pipeline(json.dumps([report["reader"], {"type": "filters.crop", "polygon": wkt}]))
            expected = reference.execute_streaming(65_536)
            if args.invert:
                expected = int(meta["num_points"]) - expected
            report["reference_kind"] = "bounded full-resolution PDAL crop"
        else:
            reference = pdal.Pipeline(json.dumps([read]))
            reference.execute()
            points = reference.arrays[0]
            # Independent triangle inequality; no Shapely and no preview inputs.
            mask = ((points["X"] >= x) & (points["Y"] >= y) &
                    ((points["X"] - x) + (points["Y"] - y) <= width))
            if args.invert:
                mask = ~mask
            expected = int(mask.sum())
            codes, counts = np.unique(points["Classification"][mask], return_counts=True)
            report["classification_reference_passed"] = result.classification_counts == tuple(
                (int(c), int(n)) for c, n in zip(codes, counts))
            report["reference_kind"] = "all original fixture points, independent triangle predicate"
        report["expected_count"] = expected
        report["inverted"] = args.invert
        if args.invert:
            ordinary = replace(definition, selection_id="ordinary", invert_result=False)
            ordinary_count = resolver.resolve([ordinary]).resolved_point_count
            report["inverse_partition_complete"] = (
                ordinary_count + result.resolved_point_count == int(meta["num_points"]))
        else:
            added = replace(definition, selection_id="add", selection_mode="ADD")
            report["add_no_double_count"] = resolver.resolve([definition, added]).resolved_point_count == result.resolved_point_count
            subtract = replace(definition, selection_id="subtract", selection_mode="SUBTRACT")
            report["subtract_all_empty"] = resolver.resolve([definition, subtract]).resolved_point_count == 0
        source.verify()
        report["source_unchanged"] = True
        mode_checks = (report.get("inverse_partition_complete", False) if args.invert else
                       report["add_no_double_count"] and report["subtract_all_empty"])
        report["passed"] = (result.resolved_point_count == expected and expected > 0 and
                            report.get("classification_reference_passed", True) and mode_checks)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output_dir / "selection_acceptance.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
