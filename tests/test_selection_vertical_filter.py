import unittest

import numpy as np

from pyforestscan_qgis.core.adapter import _apply_selection_height_filter


class Request:
    selection_vertical_axis = "Z"
    selection_height_range = (2.0, 4.0)


class SelectionVerticalFilterTests(unittest.TestCase):
    def array(self):
        return np.array([(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)], dtype=[("Z", "f8"), ("HeightAboveGround", "f8")])

    def test_elevation_range_filters_after_normalization(self):
        result = _apply_selection_height_filter(self.array(), Request())
        self.assertEqual(len(result), 1)
        self.assertEqual(float(result["Z"][0]), 3.0)

    def test_hag_range_uses_height_above_ground_dimension(self):
        request = Request()
        request.selection_vertical_axis = "HeightAboveGround"
        request.selection_height_range = (3.0, 5.0)
        result = _apply_selection_height_filter(self.array(), request)
        self.assertEqual(len(result), 1)
        self.assertEqual(float(result["HeightAboveGround"][0]), 4.0)

    def test_empty_range_fails_with_actionable_message(self):
        request = Request()
        request.selection_height_range = (20.0, 30.0)
        with self.assertRaisesRegex(Exception, "contains no source points"):
            _apply_selection_height_filter(self.array(), request)
