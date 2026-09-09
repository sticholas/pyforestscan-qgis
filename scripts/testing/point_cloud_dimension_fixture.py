"""Create a bounded QA derivative with NIR, precise Extra Bytes and a custom VLR."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.source.stat().st_size > 100_000_000:
        raise ValueError("Use a small fixture and a new destination.")
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    reader = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(args.source)}]))
    reader.execute()
    original = reader.arrays[0]
    points = np.empty(len(original), dtype=original.dtype.descr + [("Infrared", "u2"), ("FutureScore", "f8"), ("TreeID", "u8")])
    for name in original.dtype.names:
        points[name] = original[name]
    points["Infrared"] = np.arange(len(points)) % 65536
    points["FutureScore"] = np.arange(len(points)) / 7
    points["TreeID"] = 2**53 + np.arange(len(points), dtype=np.uint64)
    index = np.arange(len(points))
    for name, divisor in (("Synthetic", 2), ("KeyPoint", 3), ("Overlap", 7), ("Withheld", 11)):
        points[name] = (index % divisor == 0)
    points["ReturnNumber"] = 1 + index % 3
    points["NumberOfReturns"] = 3
    points["PointSourceId"] = index % 65535
    points["GpsTime"] = 1_000_000 + index / 8
    options = {"type": "writers.las", "filename": str(args.output), "minor_version": 4,
        "dataformat_id": 8, "a_srs": "EPSG:32605", "extra_dims": "all",
        "scale_x": .001, "scale_y": .001, "scale_z": .001,
        "vlrs": [{"user_id": "PFS_QA", "record_id": 42, "description": "Preserve payload",
                  "data": base64.b64encode(b"non-destructive editing custom VLR").decode()}]}
    writer = pdal.Pipeline(json.dumps([options]), arrays=[points])
    assert writer.execute_streaming(65536) == len(points)
    print(json.dumps({"fixture": str(args.output), "points": len(points),
        "extra_dimensions": ["Infrared", "FutureScore", "TreeID"], "custom_vlr": "PFS_QA:42"}))


if __name__ == "__main__":
    main()
