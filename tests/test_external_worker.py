"""Tests for external worker job specs and subprocess execution."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_executor import BatchExecutor
from pyforestscan_qgis.core.batch_runner import BatchExecutionError
from pyforestscan_qgis.core.external_worker import (
    EXTERNAL_WORKER_ENABLE_ENV,
    EXTERNAL_WORKER_MODE,
    build_worker_job_spec,
    external_workers_enabled,
    load_worker_job_spec,
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

    def test_external_workers_disabled_by_default(self) -> None:
        """External workers require an explicit developer flag."""
        with patch.dict("os.environ", {EXTERNAL_WORKER_ENABLE_ENV: ""}, clear=False):
            self.assertFalse(external_workers_enabled())

    def test_external_executor_blocked_without_developer_flag(self) -> None:
        """External mode cannot launch subprocesses during normal plugin use."""
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

            with patch.dict("os.environ", {EXTERNAL_WORKER_ENABLE_ENV: ""}, clear=False):
                with self.assertRaises(BatchExecutionError) as raised:
                    BatchExecutor().run(request)

            self.assertIn("External worker mode is disabled", str(raised.exception))
            self.assertFalse((root / "out").exists())

    def test_external_guardrail_blocked_without_developer_flag(self) -> None:
        """Guardrails refuse external mode before any worker command is built."""
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
                    max_workers=2,
                    confirm_large_parallel=True,
                ),
            )

            with patch.dict("os.environ", {EXTERNAL_WORKER_ENABLE_ENV: ""}, clear=False):
                report = BatchExecutor().guardrails(request)

            self.assertTrue(report.blocked)
            self.assertFalse(report.is_external)
            self.assertIn("disabled", report.reason or "")


if __name__ == "__main__":
    unittest.main()
