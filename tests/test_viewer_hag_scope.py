"""Regression tests for selection-bounded viewer HAG preparation."""
from types import SimpleNamespace
import unittest

from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import _pipeline
from pyforestscan_qgis.viewer.editor_worker import (
    ViewerPreparationRequest,
    _selection_preparation_bounds,
    _active_view_preparation_bounds,
)


class ViewerHagScopeTests(unittest.TestCase):
    def test_selection_bounds_use_xy_envelope_not_source_point_count(self):
        result = SimpleNamespace(bounds=(10.0, 20.0, 1.0, 30.0, 40.0, 9.0))
        self.assertEqual(
            _selection_preparation_bounds(result),
            {"xmin": 10.0, "ymin": 20.0, "xmax": 30.0, "ymax": 40.0},
        )

    def test_empty_selection_has_no_preparation_bounds(self):
        self.assertIsNone(_selection_preparation_bounds(None))
        self.assertIsNone(_selection_preparation_bounds(SimpleNamespace(bounds=None)))

    def test_area_detail_bounds_apply_without_a_selection(self):
        self.assertEqual(
            _active_view_preparation_bounds({
                "view_type": "AREA_DETAIL",
                "geometry": {"shape": "RECTANGLE", "center": (100.0, 200.0), "width": 40.0, "height": 20.0},
            }),
            {"xmin": 80.0, "ymin": 190.0, "xmax": 120.0, "ymax": 210.0},
        )

    def test_vertical_slice_bounds_include_its_corridor_width(self):
        self.assertEqual(
            _active_view_preparation_bounds({
                "view_type": "VERTICAL_SLICE",
                "geometry": {"a": (10.0, 20.0), "b": (30.0, 50.0), "thickness": 4.0},
            }),
            {"xmin": 8.0, "ymin": 18.0, "xmax": 32.0, "ymax": 52.0},
        )

    def test_overview_does_not_authorize_whole_source_hag(self):
        self.assertIsNone(_active_view_preparation_bounds({"view_type": "OVERVIEW_3D", "geometry": {}}))

    def test_viewer_request_carries_bounded_hag_scope(self):
        request = ViewerPreparationRequest(
            input_path="source.laz",
            source_dimensions=("X", "Y", "Z", "Classification"),
            bounds={"xmin": 10.0, "ymin": 20.0, "xmax": 30.0, "ymax": 40.0},
        )
        self.assertEqual(request.bounds["xmin"], 10.0)

    def test_las_hag_pipeline_crops_before_height_normalization(self):
        assessment = SimpleNamespace(
            source="source.laz",
            crs=None,
            coordinate_units=SimpleNamespace(from_meters=lambda value: value),
        )
        plan = SimpleNamespace(height_mode=__import__(
            "pyforestscan_qgis.core.lidar_preparation",
            fromlist=["HeightNormalizationPlanMode"],
        ).HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND)
        stages = _pipeline(
            assessment,
            plan,
            "prepared.laz",
            {"xmin": 10.0, "ymin": 20.0, "xmax": 30.0, "ymax": 40.0},
        )
        self.assertEqual(stages[1]["type"], "filters.crop")
        self.assertEqual(stages[1]["bounds"], "([10.0,30.0],[20.0,40.0])")
        self.assertEqual(stages[-2]["type"], "filters.hag_delaunay")


if __name__ == "__main__":
    unittest.main()
