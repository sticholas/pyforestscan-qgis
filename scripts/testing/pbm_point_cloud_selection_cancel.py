#!/usr/bin/env python3
"""Measure cooperative Brush cancellation against an immutable local source."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import threading
from time import monotonic
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=0.02)
    parser.add_argument("--segments", type=int, default=512)
    args = parser.parse_args()
    if not 2 <= args.segments <= 512 or args.delay < 0:
        parser.error("segments must be 2-512 and delay must be non-negative")

    import pdal
    from pyproj import CRS
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver, brush_selection
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity

    identity = SourceIdentity.capture(args.source)
    pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(args.source)}]))
    metadata = next(iter(pipeline.quickinfo.values()))
    bounds = metadata["bounds"]
    srs = metadata.get("srs", {})
    wkt = srs.get("compoundwkt") or srs.get("wkt") or ""
    crs = CRS.from_user_input(wkt) if wkt else None
    authority = crs.to_authority() if crs else None
    crs_text = ":".join(authority) if authority else (crs.to_wkt() if crs else "SOURCE_LOCAL:" + identity.sha256)

    xmin, xmax = float(bounds["minx"]), float(bounds["maxx"])
    ymin, ymax = float(bounds["miny"]), float(bounds["maxy"])
    width, height = xmax-xmin, ymax-ymin
    path = tuple((xmin + width*i/(args.segments-1),
                  ymin + height*(0.35 if i % 2 else 0.65)) for i in range(args.segments))
    radius = max(min(width, height) / (args.segments * 4), 0.001)
    base = SelectionDefinition(uuid4().hex, uuid4().hex, identity.sha256,
        identity.source_type, ((xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax),(xmin,ymin)), crs_text)
    definition = brush_selection(base, path=path, radius=radius)
    resolver = SelectionResolver(identity)

    cancelled = threading.Event()
    requested_at = [None]
    counts = []
    timer = [None]
    def request_cancel():
        requested_at[0] = monotonic()
        cancelled.set()
    def progress(count):
        counts.append(count)
        if timer[0] is None:
            timer[0] = threading.Timer(args.delay, request_cancel)
            timer[0].start()

    started = monotonic()
    error = None
    try:
        resolver.resolve([definition], cancelled=cancelled.is_set, progress=progress)
    except InterruptedError as caught:
        error = str(caught)
    finished = monotonic()
    if timer[0] is not None:
        timer[0].join()
    identity.verify()
    report = {
        "passed": bool(error and requested_at[0] is not None),
        "source": str(args.source),
        "source_identity": asdict(identity),
        "segments": args.segments,
        "radius": radius,
        "progress_counts": counts,
        "error": error,
        "elapsed_seconds": finished-started,
        "cancel_latency_seconds": finished-requested_at[0] if requested_at[0] is not None else None,
        "original_verified_unchanged": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
