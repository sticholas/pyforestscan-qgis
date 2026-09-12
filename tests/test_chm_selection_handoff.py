import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.pipeline import _selection_request_kwargs
from pyforestscan_qgis.core.pipeline_context import PipelineContextError, load_pipeline_contexts
from pyforestscan_qgis.core.point_cloud.selection_product_request import SelectionProductRequest
from pyforestscan_qgis.core.types import ProductType


class ChmSelectionHandoffTests(unittest.TestCase):
    def _context(self, status=None):
        request = SelectionProductRequest(
            selection_id="s1", source_path=Path("forest.laz"), source_fingerprint="a" * 64,
            product=ProductType.CHM, scope_kind="AREA",
            geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
            geometry_crs="EPSG:32604", bounds=(0.0, 0.0, 10.0, 8.0), vertical_axis="Z",
            z_range=(2.0, 20.0), hag_range=None, point_count=100, output_folder=Path("outputs"),
            review_required=False, review_reason="",
        )
        payload = {"source_dataset": "forest.laz", "selection_scope": request.to_dict(), "products": [{"product": "chm", "requested": True}]}
        if status is not None:
            payload["selection_execution"] = {"status": status}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_pipeline_contexts(path, Path(folder))[0]

    def test_ready_scope_passes_existing_bounded_fields(self):
        values = _selection_request_kwargs(self._context("READY_FOR_EXECUTION"))
        self.assertEqual(values["bounds"], ((0.0, 0.0), (10.0, 8.0)))
        self.assertEqual(values["selection_vertical_axis"], "Z")
        self.assertEqual(values["selection_height_range"], (2.0, 20.0))
        self.assertEqual(values["polygon_execution_input"].source_kind, "viewer_selection")

    def test_review_scope_fails_closed(self):
        with self.assertRaises(PipelineContextError):
            _selection_request_kwargs(self._context("REVIEW_ONLY"))

    def test_whole_dataset_keeps_existing_empty_request(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = {"source_dataset": "forest.laz", "products": [{"product": "chm", "requested": True}]}
            path = Path(folder) / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            context = load_pipeline_contexts(path, Path(folder))[0]
        self.assertEqual(_selection_request_kwargs(context), {})
