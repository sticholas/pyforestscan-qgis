"""Managed-runtime preparation audit; original files are read-only."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan import filters
    before = digest(args.source)
    report = {"source": str(args.source), "source_sha256": before,
              "pyforestscan_version": importlib.metadata.version("pyforestscan"),
              "filters_sha256": digest(Path(filters.__file__)),
              "scope": "In-memory filter qualification, not workspace integration or file export",
              "checks": [], "passed": False}
    try:
        pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(args.source)}]))
        info = next(iter(pipeline.quickinfo.values()))
        if info["num_points"] > 250000:
            raise ValueError("This bounded audit fixture must contain at most 250,000 points.")
        pipeline.execute()
        original = pipeline.arrays[0]
        dtype = original.dtype.descr + [("AuditRecordId", "u8")]
        source = np.empty(len(original), dtype=dtype)
        for field in original.dtype.names:
            source[field] = original[field]
        source["AuditRecordId"] = np.arange(len(source))
        baseline = source.copy()
        for name, call in (
            ("poisson_radius_0.5", lambda data: filters.downsample_poisson(data, .5)),
            ("voxel_first_0.5", lambda data: filters.downsample_voxel(data, .5, "first")),
            ("hag_delaunay", lambda data: filters.add_height_above_ground(data, method="delaunay")),
        ):
            started = time.monotonic()
            result = np.concatenate(call([source.copy()]))
            ids = result["AuditRecordId"].astype(np.int64)
            assert len(result) > 0 and len(np.unique(ids)) == len(ids)
            assert np.all((ids >= 0) & (ids < len(source)))
            for field in original.dtype.names:
                if field == "HeightAboveGround" and name == "hag_delaunay":
                    continue
                assert np.array_equal(result[field], source[field][ids]), field
            assert np.array_equal(source, baseline)
            if name == "hag_delaunay":
                assert len(result) == len(source)
                assert np.all(np.isfinite(result["HeightAboveGround"]))
            else:
                assert len(result) < len(source)
            report["checks"].append({"operation": name, "input_points": len(source),
                "output_points": len(result), "seconds": time.monotonic()-started,
                "original_attributes_preserved": True, "input_array_unchanged": True,
                "dimensions": list(result.dtype.names)})
        report["source_unchanged"] = digest(args.source) == before
        assert report["source_unchanged"]
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (args.output_dir / "preparation-evidence.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
