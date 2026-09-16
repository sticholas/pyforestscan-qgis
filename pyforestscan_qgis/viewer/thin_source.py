"""Managed, non-destructive LAS/LAZ thinning worker."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.point_cloud.preparation import PreparationRequest
from pyforestscan_qgis.core.point_cloud.preparation_execution import prepare_arrays
from pyforestscan_qgis.core.point_cloud.preparation_publication import stage_preparation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--cancel-file", type=Path)
    args = parser.parse_args()
    started = time.monotonic()

    def cancelled():
        return bool(args.cancel_file and args.cancel_file.exists())

    def progress(stage):
        if cancelled():
            raise InterruptedError("Thinning cancelled.")
        if args.progress_file:
            atomic_write_json(args.progress_file, {
                "stage": stage,
                "elapsed_seconds": round(time.monotonic() - started, 1),
            })

    request = PreparationRequest.from_dict(json.loads(args.request.read_text(encoding="utf-8")))
    progress("Verifying original source")
    request.verify_input(cancelled=cancelled)
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    try:
        import pdal
        import pyforestscan.filters as filters
        progress("Reading full-resolution source")
        pipeline = pdal.Pipeline(json.dumps({
            "pipeline": [{"type": "readers.las", "filename": request.source.path}]
        }))
        pipeline.execute()
        arrays = tuple(pipeline.arrays or ())
        progress("Applying thinning")
        prepared = prepare_arrays(arrays, request.options, filters_module=filters,
                                  cancelled=cancelled, progress=progress)
        with stage_preparation(request, cancelled=cancelled) as transaction:
            progress("Writing validated point-cloud copy")
            writer = {
                "type": "writers.las", "filename": str(transaction.staged),
                "compression": "laszip" if transaction.staged.suffix.lower() == ".laz" else "none",
                "extra_dims": "all",
            }
            output_pipeline = pdal.Pipeline(json.dumps({"pipeline": [writer]}),
                                            arrays=list(prepared.arrays))
            output_pipeline.execute()
            progress("Validating thinned copy")
            def validate(path):
                info = next(iter(pdal.Pipeline(json.dumps({
                    "pipeline": [{"type": "readers.las", "filename": str(path)}]
                })).quickinfo.values()))
                count = int(info.get("num_points", 0))
                return {"status": "VALIDATED", "point_count": count,
                        "expected_point_count": prepared.output_points,
                        "dimensions": info.get("dimensions", "")} if count == prepared.output_points else {
                            "status": "INVALID", "point_count": count,
                            "expected_point_count": prepared.output_points}
            report = transaction.publish(validate, cancelled=cancelled)
        result = {
            "status": "COMPLETE", "output_path": request.output_path,
            "provenance_path": str(request.provenance_path),
            "input_points": prepared.input_points, "output_points": prepared.output_points,
            "reduction_percent": round(100 * (1 - prepared.output_points / prepared.input_points), 2),
            "source_unchanged": report["source_unchanged"],
        }
        atomic_write_json(args.result, result)
        print(json.dumps(result, sort_keys=True), flush=True)
    finally:
        if dll_handle:
            dll_handle.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
