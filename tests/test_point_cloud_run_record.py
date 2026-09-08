"""Durable lifecycle diagnostics, independent of QGIS/Qt and the renderer."""
import json
from pathlib import Path
import tempfile
import unittest
from pyforestscan_qgis.core.point_cloud.run_record import ViewerRunRecord


class ViewerRunRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.record = ViewerRunRecord(Path(self.temp.name), "tiny.copc.laz")

    def test_attempts_are_distinct(self):
        other = ViewerRunRecord(Path(self.temp.name), "tiny.copc.laz")
        self.assertNotEqual(self.record.folder, other.folder)

    def test_logs_exist_before_any_child_launch(self):
        for name in ("stdout.log", "stderr.log", "prepare_stdout.log", "prepare_stderr.log"):
            self.assertTrue((self.record.folder / name).is_file())

    def test_unfinished_record_does_not_invent_crash_or_exit(self):
        self.record.stage("SOURCE_OPENED")
        data = json.loads(self.record.path.read_text())
        self.assertEqual(data["last_successful_stage"], "SOURCE_OPENED")
        self.assertIsNone(data["exit_code"])
        self.assertIsNone(data["finished_at"])

    def test_clean_shutdown_is_distinct_from_failure(self):
        self.record.shutdown("test_harness")
        self.record.finish(0)
        self.assertEqual(self.record.data["viewer_stage"], "SHUTDOWN_COMPLETE")
        self.assertEqual(self.record.data["shutdown_origin"], "test_harness")
        self.assertIsNone(self.record.data["exception_message"])

    def test_failure_retains_exact_exception_and_last_stage(self):
        self.record.stage("FIRST_FRAME_RENDERED")
        try:
            raise RuntimeError("wrapped C/C++ object of type ViewerWorker has been deleted")
        except RuntimeError as error:
            self.record.finish(1, error)
        data = json.loads(self.record.path.read_text())
        self.assertEqual(data["last_successful_stage"], "FIRST_FRAME_RENDERED")
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["exception_type"], "RuntimeError")
        self.assertIn("ViewerWorker", data["traceback"])

    def test_error_lists_are_bounded(self):
        for i in range(110):
            self.record.observe({"JS_console_messages": str(i)})
        self.assertEqual(len(self.record.data["JS_console_messages"]), 100)

    def test_stage_must_be_known(self):
        with self.assertRaises(ValueError):
            self.record.stage("GUESS_RENDERER_CRASH")

    def test_harness_never_polls_deleted_qt_worker(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "scripts/testing/qgis_point_cloud_viewer_smoke.py").read_text()
        self.assertIn("stopped.is_set()", text)
        self.assertNotIn(".isRunning()", text)


if __name__ == "__main__":
    unittest.main()
