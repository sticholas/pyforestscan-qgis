"""Regression coverage for polygon dispatch handoff diagnostics."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.launch_attempt import append_attempt_stage, create_launch_attempt, read_attempt_status


class Phase32FDispatchTests(unittest.TestCase):
    def test_concurrent_stage_writes_preserve_every_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global.json"):
                attempt = create_launch_attempt(root, ("pai", "fhd"), "plan")
                threads = [threading.Thread(target=append_attempt_stage, args=(attempt, f"STAGE_{index}")) for index in range(40)]
                for thread in threads: thread.start()
                for thread in threads: thread.join()
            payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
            stages = {entry["stage"] for entry in payload["stages"]}
            self.assertTrue({f"STAGE_{index}" for index in range(40)} <= stages)
            for entry in payload["stages"][1:]:
                self.assertIn("elapsed_ms", entry)
                self.assertIn("thread_id", entry)
                self.assertIn("qgis_main_thread", entry)

    def test_dispatch_is_launching_until_background_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global.json"):
                attempt = create_launch_attempt(root, ("pai",), "plan")
                append_attempt_stage(attempt, "DISPATCH_STARTED")
                self.assertEqual(json.loads(attempt.trace_path.read_text(encoding="utf-8"))["outcome"], "LAUNCHING")
                append_attempt_stage(attempt, "FIRST_WORKER_STARTED")
            self.assertEqual(json.loads(attempt.trace_path.read_text(encoding="utf-8"))["outcome"], "RUNNING")

    def test_launch_stall_requires_missing_background_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global.json"):
                attempt = create_launch_attempt(root, ("pai",), "plan")
                payload = json.loads(attempt.trace_path.read_text(encoding="utf-8"))
                payload["clicked_at"] = "2020-01-01T00:00:00+00:00"
                attempt.trace_path.write_text(json.dumps(payload), encoding="utf-8")
                append_attempt_stage(attempt, "DISPATCH_STARTED")
                self.assertTrue(read_attempt_status(attempt)["stalled"])
                append_attempt_stage(attempt, "WORKER_STARTED")
                self.assertFalse(read_attempt_status(attempt)["stalled"])

    def test_worker_start_is_inside_exception_boundary_and_dispatch_precedes_thread_start(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        worker = source[source.index("class _PolygonBatchExecutionWorker"):source.index("class _BackendInstallWorker")]
        self.assertLess(worker.index("try:"), worker.index('append_attempt_stage(self.launch_attempt, "WORKER_STARTED"'))
        launch = source[source.index("    def _run_polygon_batch"):source.index("    def _build_batch_request", source.index("    def _run_polygon_batch"))]
        self.assertLess(launch.index('append_attempt_stage(launch_attempt, "DISPATCH_STARTED"'), launch.index("self.batch_thread.start()"))
        self.assertIn("record_polygon_dispatch_validation", launch)

    def test_generic_polygon_route_launches_managed_coordinator_before_preparation(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn("_submit_and_observe_generic_polygon", source)
        submit = source[source.index("def _submit_and_observe_generic_polygon"):source.index("def write_polygon_batch_manifest")]
        self.assertIn('"COORDINATOR_PROCESS_CREATED"', submit)
        self.assertIn("generic=True", submit)
        coordinator = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/backend_runner/generic_polygon_coordinator.py").read_text(encoding="utf-8")
        self.assertIn('PYFORESTSCAN_GENERIC_POLYGON_COORDINATOR', coordinator)
        self.assertIn('stop.wait(5)', coordinator)
        self.assertIn('cancel_requested.json', coordinator)
        self.assertIn('BatchExecutor(adapter_factory=lambda: PyForestScanAdapter(execution_mode="qgis_python"))', source)


if __name__ == "__main__":
    unittest.main()
