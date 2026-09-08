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
    args = parser.parse_args()
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver, reader_spec
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
        if args.large:
            if source.source_type != "COPC":
                raise ValueError("Large qualification must use indexed COPC.")
            x, y = (xmin + xmax) / 2, (ymin + ymax) / 2
            width = min(10, (xmax - xmin) / 4, (ymax - ymin) / 4)
        else:
            if not 0 < meta["num_points"] <= 2_000_000:
                raise ValueError("Full-reference test is limited to small fixtures.")
            x, y = xmin, ymin
            width = min(xmax - xmin, ymax - ymin) * .55
        ring = ((x, y), (x + width, y), (x, y + width), (x, y))
        definition = SelectionDefinition("triangle", "qualification", source.sha256,
                                         source.source_type, ring, crs)
        resolver = SelectionResolver(source)
        result = resolver.resolve([definition])
        report["result"] = asdict(result)
        report["reader"] = reader_spec(source, [definition])
        if args.large:
            # Independently resolve with PDAL's own crop stage, not a display LOD.
            wkt = "POLYGON ((" + ", ".join(f"{px} {py}" for px, py in ring) + "))"
            reference = pdal.Pipeline(json.dumps([report["reader"], {"type": "filters.crop", "polygon": wkt}]))
            expected = reference.execute_streaming(65_536)
            report["reference_kind"] = "bounded full-resolution PDAL crop"
        else:
            reference = pdal.Pipeline(json.dumps([read]))
            reference.execute()
            points = reference.arrays[0]
            # Independent triangle inequality; no Shapely and no preview inputs.
            mask = ((points["X"] >= x) & (points["Y"] >= y) &
                    ((points["X"] - x) + (points["Y"] - y) <= width))
            expected = int(mask.sum())
            codes, counts = np.unique(points["Classification"][mask], return_counts=True)
            report["classification_reference_passed"] = result.classification_counts == tuple(
                (int(c), int(n)) for c, n in zip(codes, counts))
            report["reference_kind"] = "all original fixture points, independent triangle predicate"
        report["expected_count"] = expected
        added = replace(definition, selection_id="add", selection_mode="ADD")
        report["add_no_double_count"] = resolver.resolve([definition, added]).resolved_point_count == result.resolved_point_count
        subtract = replace(definition, selection_id="subtract", selection_mode="SUBTRACT")
        report["subtract_all_empty"] = resolver.resolve([definition, subtract]).resolved_point_count == 0
        source.verify()
        report["source_unchanged"] = True
        report["passed"] = (result.resolved_point_count == expected and expected > 0 and
                            report.get("classification_reference_passed", True) and
                            report["add_no_double_count"] and report["subtract_all_empty"])
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output_dir / "selection_acceptance.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
