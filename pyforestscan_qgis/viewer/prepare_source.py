"""Bounded local LAS/LAZ viewer-cache preparation inside scientific Python."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import struct
from uuid import uuid4

MAX_UNINDEXED_POINTS = 2_000_000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if source.suffix.lower() not in (".las", ".laz"):
        raise ValueError("Select a LAS or LAZ source.")
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import pdal
    before = source.stat()
    with source.open("rb") as stream:
        header = stream.read(227)
    if len(header) < 227 or header[:4] != b"LASF":
        raise ValueError("Invalid LAS public header.")
    transforms = struct.unpack_from("<6d", header, 131)
    pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(source)}]))
    info = pipeline.quickinfo
    metadata = next(iter(info.values()))
    count = int(metadata.get("num_points", 0))
    if count <= 0:
        raise ValueError("Source has no cheaply verified point count.")
    if count > MAX_UNINDEXED_POINTS:
        raise ValueError("Large unindexed LAS/LAZ requires an out-of-core viewer index. Open COPC/EPT; the source has not been loaded or modified.")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / (digest.hexdigest() + "-v1.copc.laz")
    if not destination.is_file():
        temporary = cache / (uuid4().hex + ".copc.laz")
        try:
            conversion = pdal.Pipeline(json.dumps([
                {"type": "readers.las", "filename": str(source)},
                {"type": "writers.copc", "filename": str(temporary), "forward": "all",
                 **{f"scale_{axis}": transforms[i] for i, axis in enumerate("xyz")},
                 **{f"offset_{axis}": transforms[i + 3] for i, axis in enumerate("xyz")}},
            ]))
            converted = conversion.execute()
            if converted != count or not temporary.is_file():
                raise ValueError("Viewer cache point count did not match the source.")
            if (source.stat().st_size, source.stat().st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                raise ValueError("Source changed during viewer cache preparation.")
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
    if (source.stat().st_size, source.stat().st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError("Source changed while opening.")
    print(json.dumps({"source": str(source), "render_source": str(destination),
                      "sha256": digest.hexdigest(), "point_count": count,
                      "metadata": metadata}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
