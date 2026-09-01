#!/usr/bin/env python3
"""Isolated Phase 32N EPT and cache benchmark; never used by plugin runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path


def _memory() -> int | None:
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return None


def _run(label: str, pipeline_json: dict, *, streaming: bool = False) -> tuple[dict, object | None]:
    import pdal
    started = time.perf_counter()
    before = _memory()
    try:
        pipeline = pdal.Pipeline(json.dumps(pipeline_json))
        points = pipeline.execute_streaming(65_536) if streaming else pipeline.execute()
        arrays = None if streaming else pipeline.arrays
        dimensions = [] if not arrays else list(arrays[0].dtype.names or ())
        status = "PASS"
        error = ""
    except Exception as exc:
        points = 0; arrays = None; dimensions = []; status = "UNSUPPORTED_OR_FAILED"; error = str(exc)
    after = _memory()
    return ({
        "label": label,
        "status": status,
        "wall_seconds": time.perf_counter() - started,
        "points": int(points),
        "dimensions": dimensions,
        "rss_before": before,
        "rss_after": after,
        "rss_delta": None if before is None or after is None else after - before,
        "error": error,
    }, arrays)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ept", required=True)
    parser.add_argument("--bounds", required=True, help="PDAL bounds expression")
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = str(args.ept)
    base_reader = {"type": "readers.ept", "filename": source, "bounds": args.bounds, "requests": 4}
    results: list[dict] = []
    direct, arrays = _run("direct_bounded_readers_ept", {"pipeline": [base_reader]})
    results.append(direct)
    streamed, _ = _run("streaming_readers_ept_to_null", {"pipeline": [base_reader, {"type": "writers.null"}]}, streaming=True)
    results.append(streamed)
    limited_reader = {**base_reader, "dimensions": "X,Y,Z,HeightAboveGround,Classification"}
    limited, _ = _run("limited_dimensions_if_supported", {"pipeline": [limited_reader]})
    results.append(limited)

    cache_key = hashlib.sha256(json.dumps({"source": source, "bounds": args.bounds, "dimensions": ["X", "Y", "HeightAboveGround", "Classification"]}, sort_keys=True).encode()).hexdigest()
    cache_path = args.cache_root / cache_key[:2] / f"{cache_key}.npy"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_record = {"cache_key": cache_key, "path": str(cache_path), "status": "NOT_WRITTEN"}
    if arrays:
        import numpy as np
        names = tuple(name for name in ("X", "Y", "HeightAboveGround", "Classification") if name in (arrays[0].dtype.names or ()))
        selected = np.empty(arrays[0].shape, dtype=[(name, arrays[0].dtype.fields[name][0]) for name in names])
        for name in names:
            selected[name] = arrays[0][name]
        started = time.perf_counter(); np.save(cache_path, selected, allow_pickle=False)
        cache_record.update({"status": "WRITTEN", "write_seconds": time.perf_counter() - started, "bytes": cache_path.stat().st_size, "dimensions": names})
        started = time.perf_counter(); warm = np.load(cache_path, mmap_mode="r", allow_pickle=False); _ = warm.shape
        cache_record["warm_open_seconds"] = time.perf_counter() - started
        cache_record["points"] = int(warm.shape[0])
    payload = {"schema": "phase32n-ept-benchmark-v1", "source": source, "bounds": args.bounds, "results": results, "cache": cache_record}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
