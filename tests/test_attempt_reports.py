import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchItemResult, BatchResult, batch_run_context
from pyforestscan_qgis.core.batch_results import write_batch_summaries
from pyforestscan_qgis.core.launch_attempt import create_launch_attempt, append_attempt_stage
from pyforestscan_qgis.core.job_diagnostics import write_failure_artifacts
from pyforestscan_qgis.core.batch import ProductExecutionResult


class AttemptReportTests(unittest.TestCase):
    def test_each_attempt_gets_distinct_report_and_latest_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "ept.json"
            source.write_text("{}", encoding="utf-8")
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global-latest.json"):
                first = create_launch_attempt(root, ("voxel_stat",), "plan-a")
            context = batch_run_context(source, root / "job", reuse_existing=True)
            item = BatchItemResult(source, context, "failed", "PFS_DIAGNOSTIC_SENTINEL", (), requested_products=("voxel_stat",))
            base = BatchResult("job", "Test", "2026-01-01", "2026-01-01", root, (item,), root / "batch_summary.json", root / "batch_summary.csv", root / "batch_summary.html")
            first_result = write_batch_summaries(base)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global-latest.json"):
                second = create_launch_attempt(root, ("voxel_stat",), "plan-b")
                append_attempt_stage(second, "SCIENTIFIC_FAILED", reason="different failure")
            second_result = write_batch_summaries(base)
            self.assertNotEqual(first_result.summary_html, second_result.summary_html)
            latest = json.loads((root / "latest_attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["attempt_id"], second.attempt_id)
            self.assertEqual(Path(latest["report_path"]), second_result.summary_html)
            self.assertIn(second.attempt_id, second_result.summary_html.parts)
            self.assertNotIn(first.attempt_id, second_result.summary_html.parts)

    def test_diagnostic_sentinel_bundle_preserves_traceback_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "ept.json"
            source.write_text("{}", encoding="utf-8")
            context = batch_run_context(source, root / "job", reuse_existing=True)
            item = BatchItemResult(source, context, "failed", "PFS_DIAGNOSTIC_SENTINEL", (), requested_products=("voxel_stat",), product_results=(ProductExecutionResult("voxel_stat", "FAILED", "PFS_DIAGNOSTIC_SENTINEL", (), "SENTINEL", "RuntimeError: PFS_DIAGNOSTIC_SENTINEL"),))
            result = BatchResult("job", "Sentinel", "2026-01-01", "2026-01-01", root, (item,), root / "batch_summary.json", root / "batch_summary.csv", root / "batch_summary.html", attempt_id="attempt-b", job_id="job-b")
            diagnostics = root / "diagnostics"
            diagnostics.mkdir()
            (diagnostics / "voxel_stat_failure.json").write_text(json.dumps({"exception_type": "RuntimeError", "exception": "PFS_DIAGNOSTIC_SENTINEL", "traceback": "Traceback\nRuntimeError: PFS_DIAGNOSTIC_SENTINEL"}), encoding="utf-8")
            report, bundle = write_failure_artifacts(result, diagnostics)
            self.assertIn("PFS_DIAGNOSTIC_SENTINEL", (diagnostics / "failure_summary.json").read_text(encoding="utf-8"))
            self.assertIn("PFS_DIAGNOSTIC_SENTINEL", (diagnostics / "traceback.txt").read_text(encoding="utf-8"))
            self.assertTrue(report.is_file() and bundle.is_file())

    def test_failure_summary_uses_real_work_unit_and_canonical_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "ept.json"
            source.write_text("{}", encoding="utf-8")
            run = root / "job"
            context = batch_run_context(source, run, reuse_existing=True)
            item = BatchItemResult(source, context, "failed", "empty", (), requested_products=("voxel_stat",), product_results=(ProductExecutionResult("voxel_stat", "FAILED", "empty", (), "EMPTY_EPT_READ", ""),), completed_work_units=42, total_work_units=49, failed_work_unit_id="wu-43", failure_stage="EPT_READ", work_unit_folder=str(run))
            result = BatchResult("job", "Test", "2026-01-01", "2026-01-01", root, (item,), root / "batch_summary.json", root / "batch_summary.csv", root / "batch_summary.html")
            diagnostics = root / "diagnostics"
            write_batch_summaries(result)
            write_failure_artifacts(result, diagnostics)
            payload = json.loads((diagnostics / "failure_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["work_unit_id"], "wu-43")
            self.assertEqual(payload["completed_work_units"], 42)
            self.assertNotIn("work_units/voxel_stat/work_units/voxel_stat", payload["checkpoint_path"].replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
