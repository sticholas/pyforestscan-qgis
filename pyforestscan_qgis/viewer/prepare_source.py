"""Automatic raw LAS/LAZ intake inside managed scientific Python.

Only compact metadata crosses stdout. Original points never cross the QGIS bridge.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
from pyforestscan_qgis.core.point_cloud.direct_source import direct_metadata
from pyforestscan_qgis.core.point_cloud.indexer import ViewerIndexerService, indexer_environment
from pyforestscan_qgis.core.point_cloud.indexer_resources import IndexerMemoryGuard
from pyforestscan_qgis.core.point_cloud.indexer_input import prepare_indexer_input
from pyforestscan_qgis.core.point_cloud.view_cache import ViewCache
from pyforestscan_qgis.core.point_cloud.view_policy import system_memory_pressure
from pyforestscan_qgis.core.point_cloud.view_strategy import (
    SourceViewFacts, PointCloudViewStrategyPlanner, ViewStrategy, cache_identity, cache_key,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--cancel-file", type=Path)
    args = parser.parse_args()
    started = time.monotonic()

    def cancelled():
        if args.cancel_file and args.cancel_file.exists():
            raise InterruptedError("Interactive view preparation cancelled. Reopen to restart safely.")

    def progress(stage, **values):
        cancelled()
        if args.progress_file:
            atomic_write_json(args.progress_file, {"stage": stage,
                "elapsed_seconds": round(time.monotonic() - started, 1), **values})

    def fingerprint(path):
        digest = hashlib.sha256()
        total = path.stat().st_size
        read = 0
        last = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                cancelled()
                digest.update(block)
                read += len(block)
                if time.monotonic() - last >= 1:
                    progress("Checking source identity", bytes_processed=read, bytes_total=total)
                    last = time.monotonic()
        return digest.hexdigest()

    source = args.source.resolve(strict=True)
    if source.suffix.lower() not in (".las", ".laz"):
        raise ValueError("Select a LAS or LAZ source.")
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import pdal

    def inspect(path, reader='readers.las'):
        pipeline = pdal.Pipeline(json.dumps([{"type": reader, "filename": str(path)}]))
        return next(iter(pipeline.quickinfo.values()))

    def dimensions(metadata):
        values = metadata.get("dimensions", "")
        return tuple(sorted(d.strip() for d in values.split(","))) if isinstance(values, str) else tuple(sorted(values))

    def crs(metadata):
        srs = metadata.get("srs", {})
        return srs.get("wkt", srs.get("compoundwkt", "")) if isinstance(srs, dict) else str(srs or "")

    before = source.stat()
    progress("Reading source metadata")
    metadata = inspect(source)
    count = int(metadata.get("num_points", 0))
    if count <= 0:
        raise ValueError("Source has no verified point count.")
    metadata_seconds = time.monotonic() - started
    hash_started = time.monotonic()
    digest = fingerprint(source)
    hash_seconds = time.monotonic() - hash_started
    memory = system_memory_pressure() or {}
    facts = SourceViewFacts(source.suffix[1:].upper(), before.st_size, count,
                            dimensions=dimensions(metadata), crs=crs(metadata),
                            fingerprint=digest, modified_ns=before.st_mtime_ns,
                            available_ram_bytes=memory.get("available_bytes"),
                            network=str(source).startswith(chr(92) * 2))
    direct_ok = False
    try:
        direct_metadata(source)
        direct_ok = True
    except ValueError:
        pass
    planner = PointCloudViewStrategyPlanner(direct_available=direct_ok)
    plan = planner.plan(facts)
    identity = None
    reused = False
    build_seconds = 0
    verification_seconds = 0
    if plan.strategy == ViewStrategy.DIRECT:
        destination = source
    else:
        progress("Checking optimized-view component")
        executable, prefix, version = ViewerIndexerService(resolve_backend_paths()).capability()
        identity = cache_identity(facts, version)
        cache = ViewCache(args.cache)
        cache.recover_interrupted(identity)

        def verify(path, expected):
            try:
                result = inspect(path, 'readers.copc')
                if int(result.get("num_points", -1)) != count:
                    return False
                if not set(facts.dimensions).issubset(dimensions(result)):
                    return False
                import math
                if any(not math.isclose(float(result['bounds'][key]), float(metadata['bounds'][key]),
                                        rel_tol=0, abs_tol=1e-7)
                       for key in ('minx', 'miny', 'minz', 'maxx', 'maxy', 'maxz')):
                    return False
                actual_crs = crs(result)
                if actual_crs != facts.crs:
                    from pyproj import CRS
                    if not actual_crs or not facts.crs or not CRS(actual_crs).equals(CRS(facts.crs)):
                        return False
                return True
            except (OSError, ValueError, RuntimeError, KeyError, TypeError):
                return False

        destination = cache.reusable(identity, verify)
        reused = destination is not None
        if destination is None:
            args.cache.mkdir(parents=True, exist_ok=True)
            import shutil
            needed = max(before.st_size * 4, count * 200) + 1024 ** 3
            if shutil.disk_usage(args.cache).free < needed:
                cache.cleanup(max_bytes=0, protected_keys=(cache_key(identity),))
            if shutil.disk_usage(args.cache).free < needed:
                raise RuntimeError("Not enough free space in the managed viewer cache. Free disk space and retry.")
            cache.cleanup(max_bytes=8 * 1024 ** 3, protected_keys=(cache_key(identity),))
            with cache.build(identity) as staging:
                output = staging / "view.copc.laz"
                index_input = prepare_indexer_input(source, staging, version, facts.dimensions,
                    expected_count=count, progress=progress)
                command = [str(executable), "-i", str(index_input), "-o", str(output),
                           "--temp_dir", str(staging / "index"), "--progress_debug"]
                log_path = cache.entry(identity) / "indexer.log"
                progress("Preparing an optimized interactive view", strategy=plan.strategy.value,
                         tool_version=version)
                with log_path.open("w", encoding="utf-8") as log:
                    build_started = time.monotonic()
                    child = subprocess.Popen(command, stdout=log, stderr=log,
                        env=indexer_environment(prefix), **hidden_subprocess_kwargs())
                    guard = None
                    try:
                        guard = IndexerMemoryGuard(child,
                            min(6 * 1024 ** 3, max(512 * 1024 ** 2, memory.get("available_bytes", 24 * 1024 ** 3) // 4)))
                        while child.poll() is None:
                            progress("Preparing an optimized interactive view", indexer_pid=child.pid,
                                     strategy=plan.strategy.value, progress_estimated=True)
                            time.sleep(.5)
                        if child.returncode:
                            raise RuntimeError(f"Optimized-view creation failed (exit {child.returncode}); "
                                               f"the indexer may have reached its memory limit. See {log_path}.")
                    finally:
                        if child.poll() is None:
                            child.kill()
                        child.wait()
                        if guard is not None:
                            guard.close()
                    build_seconds = time.monotonic() - build_started
                progress("Verifying optimized view")
                verification_started = time.monotonic()
                if fingerprint(source) != digest:
                    raise RuntimeError("Original source changed during view preparation.")
                destination = cache.publish(identity, output, verify=verify)
                verification_seconds = time.monotonic() - verification_started
    after = source.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError("Source changed while opening.")
    cancelled()
    strategy = ViewStrategy.REUSE_VIEW_CACHE.value if reused else plan.strategy.value
    progress("Interactive view prepared", strategy=strategy)
    compact_metadata = {"bounds": metadata.get("bounds"), "dimensions": metadata.get("dimensions"),
                        "num_points": count, "srs": {"wkt": crs(metadata)}}
    print(json.dumps({"source": str(source), "render_source": str(destination),
                      "sha256": digest, "point_count": count, "metadata": compact_metadata,
                      "strategy": strategy, "cache_fingerprint": cache_key(identity) if identity else None,
                      "timings": {"metadata_seconds": metadata_seconds, "source_hash_seconds": hash_seconds,
                                  "index_seconds": build_seconds, "verification_seconds": verification_seconds},
                      "preparation_seconds": round(time.monotonic() - started, 3)}), flush=True)
    # Keep the Windows DLL directory handle alive through every PDAL call.
    if dll_handle:
        dll_handle.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
