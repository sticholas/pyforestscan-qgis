"""Generate bounded read-only QA subsets through the installed PDAL stream API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.atomic_state import atomic_write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    handle = os.add_dll_directory(str(Path(sys.executable).parent / "Library/bin")) if os.name == "nt" else None
    import pdal
    original = args.source.stat()
    report = {"source": str(args.source), "subsets": [], "original_modified": False}
    for count in (500_000, 5_000_000, 10_000_000, 50_000_000):
        path = args.output_dir / f"olaa-first-{count}.las"
        pipeline = pdal.Pipeline(json.dumps([
            {"type": "readers.las", "filename": str(args.source), "count": count},
            {"type": "writers.las", "filename": str(path), "forward": "all", "extra_dims": "all"}]))
        if not pipeline.streamable:
            raise RuntimeError("QA subset writer must support bounded streaming.")
        started = time.monotonic()
        written = pipeline.execute_streaming(chunk_size=65536)
        if written != count:
            raise RuntimeError("Unexpected subset point count.")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        facts = next(iter(pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(path)}])).quickinfo.values()))
        report["subsets"].append({"path": str(path), "points": count, "bytes": path.stat().st_size,
            "seconds": time.monotonic() - started, "sha256": digest, "bounds": facts.get("bounds")})
        atomic_write_json(args.output_dir / "fixtures.json", report)
        print(json.dumps(report["subsets"][-1]), flush=True)
    final = args.source.stat()
    report["original_modified"] = (original.st_size, original.st_mtime_ns) != (final.st_size, final.st_mtime_ns)
    atomic_write_json(args.output_dir / "fixtures.json", report)
    if handle:
        handle.close()
    if report["original_modified"]:
        raise RuntimeError("Original changed during QA subset preparation.")


if __name__ == "__main__":
    main()
