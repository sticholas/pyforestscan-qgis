#!/usr/bin/env python3
"""Managed real-source point-to-point measurement qualification."""
from __future__ import annotations

import argparse
from dataclasses import asdict
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
    import numpy as np
    from pyproj import CRS
    from pyforestscan_qgis.core.point_cloud.measurement import (
        create_area_measurement, measurement_unit_context,
        resolve_source_measurement, resolve_source_profile_measurement)
    from pyforestscan_qgis.core.point_cloud.annotation import resolve_source_annotation
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry

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
    if "HeightAboveGround" not in (first_chunk.dtype.names or ()):
        raise RuntimeError("Real HAG profile qualification requires HeightAboveGround.")
    finite = np.flatnonzero(np.isfinite(first_chunk["HeightAboveGround"]))
    if len(finite) < 2:
        raise RuntimeError("Real HAG profile qualification requires two finite points.")
    first = int(finite[np.argmin(first_chunk["HeightAboveGround"][finite])])
    ordered = finite[np.argsort(first_chunk["HeightAboveGround"][finite])][::-1]
    second = next((int(index) for index in ordered
                   if (first_chunk["X"][index],first_chunk["Y"][index]) !=
                      (first_chunk["X"][first],first_chunk["Y"][first])),None)
    if second is None:
        raise RuntimeError("Real HAG profile qualification requires distinct XY points.")
    profile = SliceGeometry(
        (float(first_chunk["X"][first]),float(first_chunk["Y"][first])),
        (float(first_chunk["X"][second]),float(first_chunk["Y"][second])),
        1.,source_crs,"HeightAboveGround")
    requested_profile = tuple((float(first_chunk["X"][index]),
        float(first_chunk["Y"][index]),float(first_chunk["HeightAboveGround"][index]))
        for index in (first,second))
    profile_progress = []
    profile_measurement = resolve_source_profile_measurement(identity,point_count,
        requested_profile,source_crs,asdict(profile),"real-source-slice","HAG Slice",
        pdal_module=pdal,crs_type=CRS,progress=profile_progress.append)
    if profile_measurement.vertical_axis != "HeightAboveGround":
        raise RuntimeError("Profile qualification did not retain its HAG axis.")
    if tuple(anchor.source_xyz for anchor in
             (profile_measurement.start,profile_measurement.end)) != tuple(
             (float(first_chunk["X"][index]),float(first_chunk["Y"][index]),
              float(first_chunk["Z"][index])) for index in (first,second)):
        raise RuntimeError("Profile anchors did not retain original source XYZ.")
    if not profile_progress or profile_progress[-1] != point_count:
        raise RuntimeError("Profile resolver did not report the complete source scan.")
    from pyforestscan_qgis.core.point_cloud.measurement import create_profile_measurement
    tree_height = create_profile_measurement(identity.sha256, source_crs,
        "real-source-slice", "HAG Slice", profile,
        (profile_measurement.start, profile_measurement.end),
        horizontal_unit=profile_measurement.horizontal_unit,
        vertical_unit=profile_measurement.vertical_unit,
        source_point_count=point_count, resolution_seconds=profile_measurement.resolution_seconds,
        purpose="TREE_HEIGHT")
    if tree_height.vertical_distance != profile_measurement.vertical_distance:
        raise RuntimeError("Tree height differs from the authoritative HAG anchor difference.")
    annotation_progress = []
    annotation = resolve_source_annotation(identity, point_count, requested[0],
        source_crs, "Real-source marker", "Managed qualification",
        pdal_module=pdal, progress=annotation_progress.append)
    if annotation.anchor.source_xyz != requested[0] or annotation.anchor.snap_distance != 0:
        raise RuntimeError("Annotation did not resolve to the exact original source point.")
    if not annotation_progress or annotation_progress[-1] != point_count:
        raise RuntimeError("Annotation resolver did not report the complete source scan.")
    if sha256(args.source) != before:
        raise RuntimeError("Measurement changed the original source.")
    print(json.dumps({"status":"PASS", "source":identity.path,
        "source_sha256":before, "source_unchanged":True,
        "source_point_count":point_count, "measurement":measurement.to_dict(),
        "area_measurement":area.to_dict(),
        "profile_measurement":profile_measurement.to_dict(),
        "tree_height":tree_height.to_dict(),
        "annotation":annotation.to_dict(),
        "progress_final":progress[-1]}, sort_keys=True))
    if handle is not None:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
