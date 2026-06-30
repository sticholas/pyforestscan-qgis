"""External worker process entrypoint for one PyForestScan batch job."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_runner import BatchRunner
from pyforestscan_qgis.core.external_worker import ExternalWorkerResult, load_worker_job_spec, utc_now, write_worker_result

REQUIRED_MODULES = ("pyforestscan", "pdal", "osgeo.gdal", "rasterio", "numpy")


def main(argv: list[str] | None = None) -> int:
    """Run worker check or one worker job."""
    parser = argparse.ArgumentParser(description="Run one PyForestScan external worker job.")
    parser.add_argument("--check", action="store_true", help="Check worker Python dependencies and exit.")
    parser.add_argument("--spec", help="Path to worker job spec JSON.")
    args = parser.parse_args(argv)
    if args.check:
        return _check()
    if not args.spec:
        parser.error("--spec is required unless --check is used")
    return _run_spec(Path(args.spec))


def _check() -> int:
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        print("MISSING " + ", ".join(missing))
        return 1
    print("READY external worker dependencies available")
    return 0


def _run_spec(spec_path: Path) -> int:
    spec = load_worker_job_spec(spec_path)
    started = utc_now()
    result_path = spec.result_path
    try:
        settings = BatchProductSettings(
            products=spec.products,
            grid_resolution=spec.grid_resolution,
            height_bin_size=spec.height_bin_size,
            chm_interpolation=spec.chm_interpolation,
            chm_interpolate_valid_region=spec.chm_interpolate_valid_region,
            chm_clean_edges=spec.chm_clean_edges,
            canopy_cover_height_threshold=spec.canopy_cover_height_threshold,
            overwrite_existing=spec.overwrite_existing,
        )
        request = BatchRequest(
            input_folder=spec.input_lidar_path.parent,
            output_folder=spec.batch_folder,
            recursive=False,
            datasets=(spec.input_lidar_path,),
            settings=settings,
            title=f"PyForestScan Worker {spec.job_id}",
            batch_folder=spec.batch_folder,
        )
        item = BatchRunner().run_dataset(spec.input_lidar_path, spec.batch_folder, request)
        worker_result = ExternalWorkerResult(
            job_id=spec.job_id,
            dataset_path=spec.input_lidar_path,
            run_folder=spec.run_folder,
            status=item.status,
            started_at=started,
            finished_at=utc_now(),
            outputs=item.outputs,
            error_message=None if item.status == "completed" else item.message,
            log_messages=(item.message,),
        )
        write_worker_result(worker_result, result_path)
        return 0 if item.status == "completed" else 2
    except Exception as exc:  # noqa: BLE001 - worker must serialize failures for QGIS.
        write_worker_result(
            ExternalWorkerResult(
                job_id=spec.job_id,
                dataset_path=spec.input_lidar_path,
                run_folder=spec.run_folder,
                status="failed",
                started_at=started,
                finished_at=utc_now(),
                outputs=(),
                error_message=str(exc),
                log_messages=(str(exc),),
            ),
            result_path,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
