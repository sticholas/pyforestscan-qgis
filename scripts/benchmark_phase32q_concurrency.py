#!/usr/bin/env python3
"""Run a controlled, opt-in frozen-request EPT concurrency benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def one(request_path: Path, root: Path, index: int) -> dict:
    folder = root / f"region-{index:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    with request_path.open("rb") as stream:
        request = pickle.load(stream)
    output = folder / "chm_buffered.tif"
    request = replace(request, output_path=output, diagnostics_path=folder / "diagnostics")
    payload = folder / "request.pkl"
    result = folder / "result.pkl"
    with payload.open("wb") as stream:
        pickle.dump(request, stream)
    command = [sys.executable, str(Path(__file__).parents[1] / "pyforestscan_qgis/backend_runner/ept_chm_subread.py"), "--payload", str(payload), "--result", str(result)]
    from pyforestscan_qgis.core.backend.process_env import build_processing_engine_environment

    env = build_processing_engine_environment(Path(sys.prefix), "windows" if os.name == "nt" else "linux")
    if os.environ.get("PYTHONPATH"):
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
    started = time.monotonic()
    from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
    from pyforestscan_qgis.core.owned_workers import process_rss_bytes

    process = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, **hidden_subprocess_kwargs(),
    )
    peak_rss = 0
    while process.poll() is None:
        peak_rss = max(peak_rss, process_rss_bytes(process.pid))
        time.sleep(0.1)
    stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started
    timing_path = folder / "diagnostics/science_timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}
    return {
        "index": index,
        "returncode": process.returncode,
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": peak_rss,
        "point_count": int(timing.get("point_count", 0) or 0),
        "ept_seconds": float(timing.get("ept_read_and_point_decode_seconds", 0) or 0),
        "pyforestscan_seconds": float(timing.get("pyforestscan_chm_seconds", 0) or 0),
        "output_sha256": checksum(output) if output.is_file() else "",
        "stderr_tail": "\n".join(stderr.splitlines()[-5:]),
    }


def one_region(region: Path, root: Path, index: int) -> dict:
    requests = sorted(region.glob("bounded_subreads/*/request.pkl"))
    if not requests:
        raise RuntimeError(f"No frozen bounded requests found below {region}")
    started = time.monotonic()
    children = [one(path, root / f"parent-{index:02d}", subindex) for subindex, path in enumerate(requests)]
    return {
        "index": index,
        "returncode": max(item["returncode"] for item in children),
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": max(item["peak_rss_bytes"] for item in children),
        "point_count": sum(item["point_count"] for item in children),
        "ept_seconds": sum(item["ept_seconds"] for item in children),
        "pyforestscan_seconds": sum(item["pyforestscan_seconds"] for item in children),
        "output_sha256": hashlib.sha256("".join(item["output_sha256"] for item in children).encode()).hexdigest(),
        "stderr_tail": "\n".join(item["stderr_tail"] for item in children if item["stderr_tail"]),
        "bounded_request_count": len(children),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, action="append", default=[], help="Frozen bounded EPT request.pkl; repeat 8-12 times")
    parser.add_argument("--region", type=Path, action="append", default=[], help="Parent work-unit directory containing bounded_subreads; repeat 8-12 times")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, action="append", default=[])
    parser.add_argument("--execute", action="store_true", help="Required safety acknowledgement; otherwise print the plan only")
    args = parser.parse_args()
    levels = tuple(dict.fromkeys(args.concurrency or [1, 2, 3, 4, 5]))
    if any(level < 1 or level > 5 for level in levels):
        parser.error("concurrency must be between 1 and 5")
    if args.request and args.region:
        parser.error("use either --request or --region, not both")
    inputs = args.region or args.request
    plan = {"inputs": [str(path) for path in inputs], "input_kind": "parent_region" if args.region else "bounded_request", "concurrency": levels, "output": str(args.output)}
    if not args.execute:
        print(json.dumps({**plan, "status": "DRY_RUN", "message": "Add --execute only after confirming no active PBM job."}, indent=2))
        return 0
    if len(inputs) < 8:
        parser.error("real benchmark requires at least eight frozen representative inputs")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    reference = None
    for level in levels:
        run_root = args.output / f"n{level}"
        if run_root.exists():
            shutil.rmtree(run_root)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=level) as pool:
            worker = one_region if args.region else one
            futures = [pool.submit(worker, path, run_root, index) for index, path in enumerate(inputs)]
            results = [future.result() for future in as_completed(futures)]
        wall = time.monotonic() - started
        ordered = sorted(results, key=lambda item: item["index"])
        hashes = [item["output_sha256"] for item in ordered]
        if reference is None:
            reference = hashes
        rows.append({
            "workers": level,
            "wall_seconds": wall,
            "regions_per_minute": len(ordered) * 60 / wall,
            "points_per_second": sum(item["point_count"] for item in ordered) / wall,
            "ept_seconds": sum(item["ept_seconds"] for item in ordered),
            "pyforestscan_seconds": sum(item["pyforestscan_seconds"] for item in ordered),
            "peak_aggregate_rss_upper_bound_bytes": sum(sorted((item["peak_rss_bytes"] for item in ordered), reverse=True)[:level]),
            "maximum_worker_rss_bytes": max((item["peak_rss_bytes"] for item in ordered), default=0),
            "failures": sum(item["returncode"] != 0 for item in ordered),
            "outputs_equivalent_to_n1": hashes == reference,
            "results": ordered,
        })
        if rows[-1]["failures"]:
            break
    t1 = rows[0]["wall_seconds"]
    for row in rows:
        row["speedup"] = t1 / row["wall_seconds"]
        row["parallel_efficiency"] = row["speedup"] / row["workers"]
    report = {**plan, "status": "COMPLETE", "rows": rows}
    (args.output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
