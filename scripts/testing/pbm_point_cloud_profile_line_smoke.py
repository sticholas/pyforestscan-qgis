"""Read-only real-PDAL qualification for Vertical Slice line selection."""
from __future__ import annotations

import argparse
from dataclasses import asdict
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
    parser.add_argument("--slice", nargs=5, type=float, required=True,
                        metavar=("AX", "AY", "BX", "BY", "THICKNESS"))
    parser.add_argument("--line", nargs=4, type=float, required=True,
                        metavar=("ALONG1", "HEIGHT1", "ALONG2", "HEIGHT2"))
    parser.add_argument("--side", choices=("ABOVE", "BELOW"), required=True)
    parser.add_argument("--axis", choices=("Z", "HeightAboveGround"), default="Z")
    args = parser.parse_args()

    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry

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
        if args.axis not in (points.dtype.names or ()):
            raise ValueError(f"Source does not contain {args.axis}.")
        quick = next(iter(pdal.Pipeline(json.dumps([reader])).quickinfo.values()))
        srs = quick.get("srs", {})
        crs = srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:" + source.sha256
        ax, ay, bx, by, thickness = args.slice
        profile = SliceGeometry((ax,ay), (bx,by), thickness, crs, args.axis)
        line = ((args.line[0],args.line[1]), (args.line[2],args.line[3]))
        definition = SelectionDefinition("profile-line", "qualification", source.sha256,
            source.source_type, profile.corridor(), crs, profile_a=profile.a,
            profile_b=profile.b, profile_thickness=profile.thickness,
            profile_axis=args.axis, depth_mode="SLICE_CORRIDOR",
            profile_line=line, profile_line_side=args.side)
        started = time.monotonic()
        result = SelectionResolver(source).resolve([definition])
        elapsed = time.monotonic() - started

        dx, dy = bx-ax, by-ay
        along = ((points["X"]-ax)*dx + (points["Y"]-ay)*dy)/profile.length
        depth = (-(points["X"]-ax)*dy + (points["Y"]-ay)*dx)/profile.length
        (x1,h1),(x2,h2) = line
        line_height = h1 + (along-x1)*(h2-h1)/(x2-x1)
        mask = ((along >= min(x1,x2)) & (along <= max(x1,x2)) &
                (np.abs(depth) <= thickness/2))
        mask &= points[args.axis] >= line_height if args.side == "ABOVE" else points[args.axis] <= line_height
        expected = int(mask.sum())
        codes, counts = np.unique(points["Classification"][mask], return_counts=True)
        expected_classes = tuple((int(code),int(count)) for code,count in zip(codes,counts))
        source.verify()
        report.update({"slice": args.slice, "line": args.line, "side": args.side,
            "axis": args.axis, "result": asdict(result), "expected_count": expected,
            "expected_classification_counts": expected_classes,
            "elapsed_seconds": elapsed, "source_unchanged": True})
        report["passed"] = (expected > 0 and result.resolved_point_count == expected and
                            result.classification_counts == expected_classes)
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
