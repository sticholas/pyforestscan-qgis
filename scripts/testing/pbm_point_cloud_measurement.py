#!/usr/bin/env python3
"""Managed real-source point-to-point measurement qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    dll = Path(sys.executable).parent/"Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None

    import pdal
    from pyproj import CRS
    from pyforestscan_qgis.core.point_cloud.measurement import (
        create_area_measurement, measurement_unit_context, resolve_source_measurement)
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity

    identity = SourceIdentity.capture(args.source)
    before = identity.sha256
    reader = {"type":"readers.copc" if identity.source_type == "COPC" else "readers.las",
              "filename":identity.path}
    pipeline = pdal.Pipeline(json.dumps([reader]))
    metadata = next(iter(pipeline.quickinfo.values()))
    point_count = int(metadata["num_points"])
    first_chunk = next(iter(pipeline.iterator(chunk_size=65_536, prefetch=0)))
    if len(first_chunk) < 2:
        raise RuntimeError("Measurement qualification requires at least two source points.")
    indexes = (0, len(first_chunk)-1)
    requested = tuple((float(first_chunk["X"][index]), float(first_chunk["Y"][index]),
                       float(first_chunk["Z"][index])) for index in indexes)
    srs = metadata.get("srs", {})
    wkt = srs.get("compoundwkt") or srs.get("wkt")
    if wkt:
        crs = CRS.from_user_input(wkt)
        authority = crs.to_authority()
        source_crs = ":".join(authority) if authority else crs.to_wkt()
    else:
        source_crs = "SOURCE_LOCAL:"+identity.sha256
    progress = []
    measurement = resolve_source_measurement(identity, point_count, requested, source_crs,
        pdal_module=pdal, crs_type=CRS, progress=progress.append)
    if tuple(anchor.source_xyz for anchor in (measurement.start, measurement.end)) != requested:
        raise RuntimeError("Resolved anchors differ from original source coordinates.")
    expected_horizontal = math.hypot(requested[1][0]-requested[0][0],
                                     requested[1][1]-requested[0][1])
    if not math.isclose(measurement.horizontal_distance, expected_horizontal, rel_tol=0, abs_tol=1e-12):
        raise RuntimeError("Measured horizontal distance differs from source-coordinate truth.")
    if not progress or progress[-1] != point_count:
        raise RuntimeError("Measurement resolver did not report the complete source scan.")
    xmin, xmax = float(first_chunk["X"].min()), float(first_chunk["X"].max())
    ymin, ymax = float(first_chunk["Y"].min()), float(first_chunk["Y"].max())
    width, height = min(10., xmax-xmin), min(10., ymax-ymin)
    if width <= 0 or height <= 0:
        raise RuntimeError("Area qualification requires nonzero source XY extent.")
    vertices = ((xmin,ymin),(xmin+width,ymin),(xmin+width,ymin+height),
                (xmin,ymin+height),(xmin,ymin))
    horizontal, _vertical, warning = measurement_unit_context(source_crs, CRS)
    area = create_area_measurement(identity.sha256, source_crs, vertices,
        horizontal_unit=horizontal, display_elevation=float(first_chunk["Z"].mean()),
        unit_warning=warning, measurement_id="real-source-area", created_at="fixed")
    if not math.isclose(area.area, width*height, rel_tol=0, abs_tol=1e-9):
        raise RuntimeError("Area differs from projected source-coordinate truth.")
    if sha256(args.source) != before:
        raise RuntimeError("Measurement changed the original source.")
    print(json.dumps({"status":"PASS", "source":identity.path,
        "source_sha256":before, "source_unchanged":True,
        "source_point_count":point_count, "measurement":measurement.to_dict(),
        "area_measurement":area.to_dict(),
        "progress_final":progress[-1]}, sort_keys=True))
    if handle is not None:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
