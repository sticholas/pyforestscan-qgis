"""Regression coverage for detached coordinator ownership and finalization."""

from __future__ import annotations

import json
import pickle
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from pyforestscan_qgis.core.coordinator_lifecycle import (
    CoordinatorHandle,
    CoordinatorLaunchResult,
    CoordinatorTerminalResult,
)
from pyforestscan_qgis.core.polygon_batch import _submit_and_observe_generic_polygon


class _LiveProcess:
    pid = 43210

    def poll(self):
        return None


class _ExitedProcess:
    pid = 43211

    def poll(self):
        return 0


def _report(batch: Path):
    products = (SimpleNamespace(value="pai"), SimpleNamespace(value="fhd"))
    token = SimpleNamespace(executable="backend-python")
    return SimpleNamespace(
        plan_signature="plan", batch_folder=batch,
        request=SimpleNamespace(products=products, runtime_token=token),
        selected_sources=(SimpleNamespace(path=Path("source.las")),),
    )


def _handle(job_dir: Path, attempt_id: str, process) -> CoordinatorHandle:
    return CoordinatorHandle(
        attempt_id, process.pid, process, "now", job_dir / "request.pkl",
        job_dir / "progress_snapshot.json", job_dir / "coordinator_result.json",
        job_dir / "cancel_requested.json", job_dir / "pause_requested.json",
        job_dir / "coordinator_identity.json", job_dir / "stdout.log", job_dir / "stderr.log",
    )


class Phase32JCoordinatorLifecycleTests(unittest.TestCase):
    def test_slow_coordinator_stays_running_and_ignores_stale_root_state(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Path(folder)
            attempt = batch / "attempts" / "attempt-current"
            root = batch / "polygon_jobs" / "generic-plan" / "coordinator"
            root.mkdir(parents=True)
            (root / "terminal_result.json").write_text('{"state":"complete"}', encoding="utf-8")
            (root / "cancel_requested.json").write_text('{"cancel_origin":"OLD"}', encoding="utf-8")
            stages = []

            class Service:
                def submit_polygon_coordinator(self, payload, job_dir, token, products, generic=False):
                    process = _LiveProcess()
                    handle = _handle(job_dir, job_dir.name, process)

                    def finish():
                        time.sleep(0.25)
                        job_dir.mkdir(parents=True, exist_ok=True)
                        (job_dir / "coordinator_identity.json").write_text(json.dumps({"attempt_id": job_dir.name, "pid": process.pid}), encoding="utf-8")
                        output_a = batch / "pai.tif"
                        output_b = batch / "fhd.tif"
                        output_a.write_bytes(b"pai")
                        output_b.write_bytes(b"fhd")
                        item = SimpleNamespace(dataset_path=Path("source.las"), status="completed", outputs=(output_a, output_b))
                        result = SimpleNamespace(items=(item,))
                        result_path = job_dir / "result.pkl"
                        with result_path.open("wb") as stream:
                            pickle.dump(result, stream)
                        (job_dir / "coordinator_result.json").write_text(json.dumps({
                            "attempt_id": job_dir.name, "status": "SUCCEEDED",
                            "datasets": {"source.las": "COMPLETED"},
                            "products": {"pai": "SUCCEEDED", "fhd": "SUCCEEDED"},
                            "outputs": [str(output_a), str(output_b)], "result_path": str(result_path),
                            "finished_at": "now", "exit_code": 0,
                        }), encoding="utf-8")

                    threading.Thread(target=finish, daemon=True).start()
                    return CoordinatorLaunchResult(True, process.pid, ("python",), handle)

            adapter = SimpleNamespace(_backend_service=lambda: Service())
            started = time.monotonic()
            result = _submit_and_observe_generic_polygon(
                _report(batch), adapter, batch,
                stage_callback=lambda stage, details: stages.append(stage),
                control_callback=lambda: None, attempt_folder=attempt,
            )
            self.assertGreaterEqual(time.monotonic() - started, 0.2)
            self.assertEqual(len(result.items), 1)
            self.assertIn("COORDINATOR_STARTED", stages)
            self.assertIn("COORDINATOR_TERMINAL_SUCCEEDED", stages)
            current = root / "attempts" / "attempt-current"
            self.assertFalse((current / "cancel_requested.json").exists())
            self.assertNotEqual(current, root)

    def test_exit_zero_without_terminal_result_is_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Path(folder)

            class Service:
                def submit_polygon_coordinator(self, payload, job_dir, token, products, generic=False):
                    process = _ExitedProcess()
                    handle = _handle(job_dir, job_dir.name, process)
                    job_dir.mkdir(parents=True, exist_ok=True)
                    (job_dir / "coordinator_identity.json").write_text("{}", encoding="utf-8")
                    return CoordinatorLaunchResult(True, process.pid, ("python",), handle)

            adapter = SimpleNamespace(_backend_service=lambda: Service())
            with self.assertRaisesRegex(RuntimeError, "COORDINATOR_RESULT_MISSING"):
                _submit_and_observe_generic_polygon(
                    _report(batch), adapter, batch,
                    control_callback=lambda: None,
                    attempt_folder=batch / "attempts" / "attempt-missing",
                )

    def test_terminal_result_rejects_attempt_aliasing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "coordinator_result.json"
            path.write_text(json.dumps({"attempt_id": "old", "status": "SUCCEEDED"}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ATTEMPT_MISMATCH"):
                CoordinatorTerminalResult.read(path, "current")

    def test_zero_output_success_is_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = Path(folder)
            attempt = batch / "attempts" / "attempt-zero"

            class Service:
                def submit_polygon_coordinator(self, payload, job_dir, token, products, generic=False):
                    process = _LiveProcess()
                    handle = _handle(job_dir, job_dir.name, process)
                    job_dir.mkdir(parents=True, exist_ok=True)
                    (job_dir / "coordinator_identity.json").write_text("{}", encoding="utf-8")
                    result_path = job_dir / "result.pkl"
                    with result_path.open("wb") as stream:
                        pickle.dump(SimpleNamespace(items=()), stream)
                    (job_dir / "coordinator_result.json").write_text(json.dumps({
                        "attempt_id": job_dir.name, "status": "SUCCEEDED", "datasets": {},
                        "products": {"pai": "SUCCEEDED", "fhd": "SUCCEEDED"}, "outputs": [],
                        "result_path": str(result_path), "finished_at": "now", "exit_code": 0,
                    }), encoding="utf-8")
                    return CoordinatorLaunchResult(True, process.pid, ("python",), handle)

            adapter = SimpleNamespace(_backend_service=lambda: Service())
            with self.assertRaisesRegex(RuntimeError, "INTERNAL_EXECUTION_STATE_ERROR"):
                _submit_and_observe_generic_polygon(
                    _report(batch), adapter, batch,
                    control_callback=lambda: None, attempt_folder=attempt,
                )

    def test_user_cancel_records_origin_in_current_attempt_only(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        self.assertIn('"cancel_origin": "USER"', source)
        self.assertIn('coordinator_root / "attempts" / attempt_id', source)

    def test_qt_worker_cannot_finalize_before_terminal_validation(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        worker = source[source.index("class _PolygonBatchExecutionWorker"):source.index("class _BackendInstallWorker")]
        self.assertLess(worker.index('"TERMINAL_RESULT_VALIDATED"'), worker.index('"FINALIZING"'))
        self.assertLess(worker.index('"FINALIZING"'), worker.index('"COMPLETED"'))

    def test_product_progress_does_not_create_dataset_rows(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        method = source[source.index("    def _on_polygon_progress"):source.index("    def _on_batch_job_update")]
        self.assertIn('event.get("entity_type") == "dataset"', method)


if __name__ == "__main__":
    unittest.main()
