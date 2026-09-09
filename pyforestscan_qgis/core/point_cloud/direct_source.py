"""Bounded raw LAS metadata for the viewer's single-node binary adapter."""
from __future__ import annotations
import math
from pathlib import Path
import struct

from .view_strategy import SourceViewFacts, PointCloudViewStrategyPlanner, ViewStrategy


def direct_metadata(path: Path):
    path = Path(path)
    with path.open("rb") as stream:
        data = stream.read(375)
    if len(data) < 375 or data[:4] != b"LASF" or data[24] != 1 or data[25] not in (2, 4):
        raise ValueError("Direct adapter requires LAS 1.2 or 1.4.")
    fmt = data[104] & 0x3f
    if fmt not in (0, 1, 2, 3, 6, 7, 8):
        raise ValueError("This point format requires indexed preparation.")
    count = struct.unpack_from("<I", data, 107)[0]
    if data[25] == 4:
        count = struct.unpack_from("<Q", data, 247)[0] or count
    limits = struct.unpack_from("<6d", data, 179)
    bounds = [limits[1], limits[3], limits[5], limits[0], limits[2], limits[4]]
    if any(not math.isfinite(v) for v in bounds):
        raise ValueError("Invalid source bounds.")
    facts = SourceViewFacts(path.suffix[1:].upper(), path.stat().st_size, count,
                            point_record_bytes=struct.unpack_from("<H", data, 105)[0],
                            bounds=tuple(bounds))
    if PointCloudViewStrategyPlanner(direct_available=True).plan(facts).strategy != ViewStrategy.DIRECT:
        raise ValueError("Source requires managed indexed preparation.")
    side = max(0.01, *(bounds[i + 3] - bounds[i] for i in range(3)))
    cube = bounds[:3] + [bounds[i] + side for i in range(3)]
    # A virtual, single-node EPT descriptor reuses the packaged full-file decoder.
    # It is not written to disk and authorizes no sibling files.
    return {"bounds": cube, "boundsConforming": bounds, "span": 128,
            "points": count, "dataType": "laszip", "hierarchyType": "json",
            "version": "1.0.0", "schema": [], "sourceStrategy": "DIRECT"}
