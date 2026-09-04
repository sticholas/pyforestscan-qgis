import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyforestscan_qgis.core.batch import BatchItemResult, BatchResult, ProductExecutionResult
from pyforestscan_qgis.core.launch_attempt import LaunchAttempt, append_attempt_stage
from pyforestscan_qgis.core.job_diagnostics import classify_exception, write_failure_artifacts
from pyforestscan_qgis.core.job_diagnostics import classify_exception, write_failure_artifacts
from pyforestscan_qgis.core.product_dependencies import PRODUCT_DEPENDENCIES
from pyforestscan_qgis.core.types import ProductType


class Phase33BExecutionHardeningTests(unittest.TestCase):
    def _result(self, statuses):
        root = Path(tempfile.mkdtemp())
        context = SimpleNamespace(run_folder=root / "run")
        products = tuple(ProductExecutionResult(name, status, name) for name, status in statuses)
        item_status = "partial_success" if any(status == "SUCCEEDED" for _, status in statuses) and any(status == "FAILED" for _, status in statuses) else "completed"
        item = BatchItemResult(root / "source.laz", context, item_status, "result", (), requested_products=tuple(name for name, _ in statuses), product_results=products)
        return BatchResult("job", "Job", "", "", root, (item,), root / "summary.json", root / "summary.csv", root / "summary.html")

    def test_product_results_derive_partial_success(self):
        result = self._result((("chm", "SUCCEEDED"), ("dtm", "FAILED"), ("pad", "SUCCEEDED")))
        self.assertEqual("PARTIAL_SUCCESS", result.scientific_outcome)
        self.assertEqual({"SUCCEEDED", "FAILED"}, {entry.status for entry in result.items[0].product_results})

    def test_every_requested_product_has_terminal_state(self):
        result = self._result((("chm", "SUCCEEDED"), ("dtm", "FAILED"), ("pad", "SKIPPED_DEPENDENCY_FAILED")))
        self.assertEqual(result.items[0].requested_products, tuple(entry.product for entry in result.items[0].product_results))
        self.assertTrue(all(entry.status in {"SUCCEEDED", "FAILED", "SKIPPED_DEPENDENCY_FAILED", "CANCELLED", "NO_DATA"} for entry in result.items[0].product_results))

    def test_launch_attempt_partial_success_is_not_completed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace = root / "attempts" / "attempt" / "launch_attempt.json"
            trace.parent.mkdir(parents=True)
            trace.write_text(json.dumps({"attempt_id": "attempt", "clicked_at": "2026-09-04T00:00:00+00:00", "outcome": "RUNNING", "stages": []}), encoding="utf-8")
            attempt = LaunchAttempt("attempt", trace.parent, trace)
            with patch("pyforestscan_qgis.core.launch_attempt._global_latest_attempt_path", return_value=root / "global.json"):
                self.assertTrue(append_attempt_stage(attempt, "PARTIAL_SUCCESS", scientific_outcome="PARTIAL_SUCCESS"))
            payload = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual("PARTIAL_SUCCESS", payload["outcome"])
            self.assertNotEqual("COMPLETED", payload["outcome"])

    def test_product_failure_is_not_processing_engine_failure(self):
        failed = ProductExecutionResult("dtm", "FAILED", "Terrain failed", error_code="PRODUCT_EXECUTION_FAILED")
        self.assertEqual("PRODUCT_EXECUTION_FAILED", failed.error_code)
        self.assertNotIn("ENGINE", failed.error_code)

    def test_release_products_are_independent_execution_requests(self):
        release_products = {ProductType.CHM, ProductType.DTM, ProductType.PAD, ProductType.PAI, ProductType.FHD, ProductType.CANOPY_COVER, ProductType.RUMPLE, ProductType.POINT_DENSITY}
        self.assertEqual(release_products, release_products.intersection(PRODUCT_DEPENDENCIES))
        self.assertTrue(all(PRODUCT_DEPENDENCIES[product] == () for product in release_products))

    def test_dtm_scalar_error_is_product_failure(self):
        error = classify_exception(RuntimeError("DTM generation failed: invalid index to scalar variable."))
        self.assertEqual("PRODUCT_EXECUTION_FAILED", error.code)
        self.assertEqual("DTM", error.stage)

    def test_partial_result_writes_human_report_and_diagnostics_zip(self):
        result = self._result((("chm", "SUCCEEDED"), ("dtm", "FAILED")))
        result.summary_json.write_text("{}", encoding="utf-8")
        result.summary_html.write_text("<html></html>", encoding="utf-8")
        artifacts = write_failure_artifacts(result, result.batch_folder / "diagnostics")
        self.assertIsNotNone(artifacts)
        report, bundle = artifacts
        self.assertTrue(report.is_file())
        self.assertTrue(bundle.is_file())
        self.assertIn("Successful products:</strong> chm", report.read_text(encoding="utf-8"))

    def test_dtm_scalar_error_is_product_failure(self):
        error = classify_exception(RuntimeError("DTM generation failed: invalid index to scalar variable."))
        self.assertEqual("PRODUCT_EXECUTION_FAILED", error.code)
        self.assertEqual("DTM", error.stage)

    def test_partial_result_writes_human_report_and_diagnostics_zip(self):
        result = self._result((("chm", "SUCCEEDED"), ("dtm", "FAILED")))
        result.summary_json.write_text("{}", encoding="utf-8")
        result.summary_html.write_text("<html></html>", encoding="utf-8")
        artifacts = write_failure_artifacts(result, result.batch_folder / "diagnostics")
        self.assertIsNotNone(artifacts)
        report, bundle = artifacts
        self.assertTrue(report.is_file())
        self.assertTrue(bundle.is_file())
        self.assertIn("Successful products:</strong> chm", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
