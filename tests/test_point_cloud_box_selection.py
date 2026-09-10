"""QGIS-free explicit box-volume selection policy tests."""
import unittest

from pyforestscan_qgis.core.point_cloud.linked_selection import (
    box_selection_error, linked_constraints, profile_line_selection_error)


class BoxSelectionTests(unittest.TestCase):
    def test_profile_line_tools_are_slice_only(self):
        self.assertEqual(profile_line_selection_error("VERTICAL_SLICE"), "")
        for kind in ("OVERVIEW_3D", "AREA_DETAIL", "UNKNOWN"):
            self.assertIn("only in a Vertical Slice", profile_line_selection_error(kind))

    def test_overview_and_detail_require_explicit_stored_height_limits(self):
        for view_type in ("OVERVIEW_3D", "AREA_DETAIL"):
            self.assertIn("requires Elevation or HAG", box_selection_error(view_type, {}))
            self.assertEqual(box_selection_error(view_type, {"z_filter": [10, 20]}), "")
            self.assertEqual(box_selection_error(view_type, {"hag_filter": [2, 8]}), "")

    def test_slice_uses_profile_rectangle_and_corridor_thickness(self):
        view = {"view_id":"slice", "title":"Slice", "view_type":"VERTICAL_SLICE",
                "geometry":{"a":[0,0], "b":[10,0], "thickness":4,
                            "crs":"EPSG:6635", "vertical_axis":"Z"}}
        profile = ((1,2),(8,2),(8,12),(1,12),(1,2))
        self.assertEqual(box_selection_error("VERTICAL_SLICE", {}), "")
        values = linked_constraints(view, profile_geometry=profile)
        self.assertEqual(values["depth_mode"], "SLICE_CORRIDOR")
        self.assertEqual(values["profile_thickness"], 4)
        self.assertEqual(values["profile_geometry"], profile)

    def test_unknown_view_fails_closed(self):
        self.assertIn("unavailable", box_selection_error("UNKNOWN", {"z_filter":[0,1]}))


if __name__ == "__main__":
    unittest.main()
