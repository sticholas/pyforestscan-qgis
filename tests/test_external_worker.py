"""Tests for external worker job specs and subprocess execution."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_executor import BatchExecutor
from pyforestscan_qgis.core.external_worker import (
    EXTERNAL_WORKER_MODE,
    build_worker_job_spec,
    check_worker_readiness,
    load_worker_job_spec,
    load_worker_result,
    write_worker_job_spec,
)
from pyforestscan_qgis.core.types import ProductType


class ExternalWorkerTests(unittest.TestCase):
    """External worker contracts remain QGIS-free."""

    def test_worker_job_spec_round_trip(self) -> None:
        """Worker specs serialize all required fields."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "sample.las"
            dataset.write_text("", encoding="utf-8")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=2.0, execution_mode=EXTERNAL_WORKER_MODE)
            spec = build_worker_job_spec("job-1", dataset, root / "batch", settings)
            path = write_worker_job_spec(spec)
            loaded = load_worker_job_spec(path)

            self.assertEqual(spec.job_id, loaded.job_id)
            self.assertEqual(dataset, loaded.input_lidar_path)
            self.assertEqual((ProductType.CHM,), loaded.products)
            self.assertEqual(2.0, loaded.grid_resolution)
            self.assertEqual(root / "batch" / "worker_results" / "job-1_result.json", loaded.result_path)

    def test_worker_readiness_reports_status(self) -> None:
        """Readiness check returns a boolean and user-facing message."""
        ok, message = check_worker_readiness(timeout_seconds=20)

        self.assertIsInstance(ok, bool)
        self.assertIsInstance(message, str)
        self.assertTrue(message)

    def test_external_executor_records_worker_failure_without_crashing(self) -> None:
        """A worker process failure becomes a failed batch item and summary."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "sample.las"
            dataset.write_text("", encoding="utf-8")
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=(dataset,),
                settings=BatchProductSettings(
                    products=(ProductType.CHM,),
                    grid_resolution=1.0,
                    execution_mode=EXTERNAL_WORKER_MODE,
                    max_workers=1,
                    confirm_large_parallel=True,
                ),
            )

            result = BatchExecutor().run(request)
            worker_results = tuple((result.batch_folder / "worker_results").glob("*_result.json"))

            self.assertEqual(1, len(result.items))
            self.assertEqual("failed", result.items[0].status)
            self.assertTrue(result.summary_json.exists())
            self.assertTrue(worker_results)
            worker_result = load_worker_result(worker_results[0])
            self.assertEqual("failed", worker_result.status)

    def test_external_executor_runs_multiple_worker_jobs(self) -> None:
        """Multiple external workers can be launched within the configured limit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            datasets = []
            for name in ("one.las", "two.las"):
                path = root / name
                path.write_text("", encoding="utf-8")
                datasets.append(path)
            request = BatchRequest(
                input_folder=root,
                output_folder=root / "out",
                recursive=False,
                datasets=tuple(datasets),
                settings=BatchProductSettings(
                    products=(ProductType.CHM,),
                    grid_resolution=1.0,
                    execution_mode=EXTERNAL_WORKER_MODE,
                    max_workers=2,
                    confirm_large_parallel=True,
                ),
            )

            result = BatchExecutor().run(request)

            self.assertEqual(2, len(result.items))
            self.assertEqual(2, result.failure_count)
            self.assertEqual(2, len(tuple((result.batch_folder / "worker_results").glob("*_result.json"))))


if __name__ == "__main__":
    unittest.main()
