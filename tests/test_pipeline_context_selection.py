import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.pipeline_context import load_pipeline_contexts
from pyforestscan_qgis.core.point_cloud.selection_product_request import SelectionProductRequest
from pyforestscan_qgis.core.types import ProductType


class PipelineContextSelectionTests(unittest.TestCase):
    def test_context_exposes_bounds_and_existing_polygon_transport(self):
        request = SelectionProductRequest(
            selection_id="s1", source_path=Path("forest.laz"), source_fingerprint="a" * 64,
            product=ProductType.CHM, scope_kind="AREA",
            geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
            geometry_crs="EPSG:32604", bounds=(0.0, 0.0, 10.0, 8.0), vertical_axis="Z",
            z_range=(2.0, 20.0), hag_range=None, point_count=100, output_folder=Path("outputs"),
            review_required=False, review_reason="",
        )
        with tempfile.TemporaryDirectory() as folder:
            plan_path = Path(folder) / "plan.json"
            plan_path.write_text(json.dumps({
                "source_dataset": "forest.laz",
                "selection_scope": request.to_dict(),
                "products": [{"product": "chm", "requested": True}],
            }), encoding="utf-8")
            context = load_pipeline_contexts(plan_path, Path(folder))[0]
        self.assertEqual(context.selection_bounds, ((0.0, 0.0), (10.0, 8.0)))
        polygon = context.selection_polygon_execution_input
        self.assertEqual(polygon.source_kind, "viewer_selection")
        self.assertEqual(polygon.processing_crs_authid, "EPSG:32604")
        self.assertIn("POLYGON", polygon.geometry_wkt)
        self.assertEqual(polygon.envelope, (0.0, 0.0, 10.0, 8.0))

