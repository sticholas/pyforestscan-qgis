import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.selection_plan import build_scoped_product_plan, write_scoped_product_plan
from pyforestscan_qgis.core.point_cloud.selection_product_request import SelectionProductRequest
from pyforestscan_qgis.core.types import ProductType


class SelectionPlanTests(unittest.TestCase):
    def setUp(self):
        self.request = SelectionProductRequest(
            selection_id="selection-1",
            source_path=Path("forest.laz"),
            source_fingerprint="a" * 64,
            product=ProductType.CHM,
            scope_kind="AREA",
            geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
            geometry_crs="EPSG:32604",
            bounds=(0.0, 0.0, 10.0, 8.0),
            vertical_axis="Z",
            z_range=(2.0, 20.0),
            hag_range=None,
            point_count=100,
            output_folder=Path("outputs"),
            review_required=False,
            review_reason="Uses authoritative selection.",
        )
        self.base = {
            "source_dataset": "forest.laz",
            "output_folder": "base_outputs",
            "processing_executed": False,
            "products": [{"product": "chm", "requested": True, "plan_status": "Ready"}],
        }

    def test_scoped_plan_contains_one_selected_product_and_scope(self):
        plan = build_scoped_product_plan(self.base, self.request)
        self.assertEqual([item["product"] for item in plan["products"]], ["chm"])
        self.assertEqual(plan["output_folder"], "outputs")
        self.assertEqual(plan["selection_scope"]["selection_id"], "selection-1")
        self.assertEqual(plan["selection_execution"]["status"], "REVIEW_ONLY")

    def test_base_plan_is_not_modified(self):
        before = json.dumps(self.base, sort_keys=True)
        build_scoped_product_plan(self.base, self.request)
        self.assertEqual(json.dumps(self.base, sort_keys=True), before)

    def test_write_creates_review_artifact_only(self):
        with tempfile.TemporaryDirectory() as folder:
            base_path = Path(folder) / "base.json"
            output_path = Path(folder) / "reports" / "selection.json"
            base_path.write_text(json.dumps(self.base), encoding="utf-8")
            result = write_scoped_product_plan(base_path, self.request, output_path)
            self.assertEqual(result, output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["selection_scope"]["source_path"], "forest.laz")
            self.assertTrue(base_path.exists())

    def test_source_mismatch_is_rejected(self):
        mismatched = dict(self.base, source_dataset="other.laz")
        with self.assertRaises(ValueError):
            build_scoped_product_plan(mismatched, self.request)
