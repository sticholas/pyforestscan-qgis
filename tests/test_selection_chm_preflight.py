import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.selection_chm_preflight import detect_selection_source_format, preflight_selection_chm
from pyforestscan_qgis.core.point_cloud.selection_product_request import SelectionProductRequest
from pyforestscan_qgis.core.point_cloud.selection_plan import promote_scoped_product_plan
from pyforestscan_qgis.core.types import ProductType


class SelectionChmPreflightTests(unittest.TestCase):
    def request(self, source=Path("forest.laz"), review=False, point_count=100):
        return SelectionProductRequest(
            selection_id="s1", source_path=source, source_fingerprint="a" * 64,
            product=ProductType.CHM, scope_kind="AREA",
            geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
            geometry_crs="EPSG:32604", bounds=(0.0, 0.0, 10.0, 8.0), vertical_axis="Z",
            z_range=(2.0, 20.0), hag_range=None, point_count=point_count,
            output_folder=Path("outputs"), review_required=review, review_reason="review",
        )

    def test_detects_supported_source_forms(self):
        self.assertEqual(detect_selection_source_format("forest.laz"), "LAS/LAZ")
        self.assertEqual(detect_selection_source_format("forest.copc.laz"), "COPC")
        self.assertEqual(detect_selection_source_format("ept.json"), "EPT")
        self.assertEqual(detect_selection_source_format("forest.txt"), "UNSUPPORTED")

    def test_ready_report_promotes_only_when_all_gates_pass(self):
        report = preflight_selection_chm(self.request(), backend_ready=True, source_exists=True)
        self.assertTrue(report.ready)
        self.assertEqual(report.execution_status, "READY_FOR_EXECUTION")
        self.assertEqual(report.blockers, ())

    def test_missing_backend_blocks(self):
        report = preflight_selection_chm(self.request(), backend_ready=False, source_exists=True)
        self.assertFalse(report.ready)
        self.assertIn("PBM backend is not READY.", report.blockers)

    def test_missing_source_and_unsupported_format_block(self):
        report = preflight_selection_chm(self.request(Path("forest.txt")), backend_ready=True, source_exists=False)
        self.assertFalse(report.ready)
        self.assertEqual(report.execution_status, "REVIEW_ONLY")
        self.assertGreaterEqual(len(report.blockers), 2)

    def test_scientific_review_blocks_profile_raster_request(self):
        report = preflight_selection_chm(self.request(review=True), backend_ready=True, source_exists=True)
        self.assertFalse(report.ready)
        self.assertIn("Scientific review", " ".join(report.blockers))

    def test_empty_selection_blocks(self):
        report = preflight_selection_chm(self.request(point_count=0), backend_ready=True, source_exists=True)
        self.assertFalse(report.ready)
        self.assertIn("no source points", " ".join(report.blockers))

    def test_ept_directory_is_supported_when_metadata_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ept.json").write_text("{}", encoding="utf-8")
            self.assertEqual(detect_selection_source_format(root), "EPT")

    def test_failed_report_cannot_promote_scoped_plan(self):
        from pyforestscan_qgis.core.point_cloud.selection_chm_preflight import SelectionChmPreflightReport
        base = {"source_dataset": "forest.laz", "products": [{"product": "chm", "requested": True}]}
        failed = SelectionChmPreflightReport(False, "LAS/LAZ", ("blocked",))
        with self.assertRaises(ValueError):
            promote_scoped_product_plan(base, self.request(), failed)

    def test_ready_report_marks_plan_executable(self):
        base = {"source_dataset": "forest.laz", "products": [{"product": "chm", "requested": True}]}
        report = preflight_selection_chm(self.request(), backend_ready=True, source_exists=True)
        plan = promote_scoped_product_plan(base, self.request(), report)
        self.assertEqual(plan["selection_execution"]["status"], "READY_FOR_EXECUTION")
        self.assertEqual(plan["selection_execution"]["source_format"], "LAS/LAZ")
