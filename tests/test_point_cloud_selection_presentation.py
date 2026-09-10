"""QGIS-free presentation contracts for intuitive selection controls."""
import unittest

from pyforestscan_qgis.core.point_cloud.selection_presentation import (
    SELECTION_COMBINE_OPTIONS, recommended_height_range,
    selection_combine_summary, selection_height_summary)


class SelectionPresentationTests(unittest.TestCase):
    def test_selection_combination_uses_plain_language_and_stable_values(self):
        self.assertEqual(SELECTION_COMBINE_OPTIONS, (
            ("Start new selection", "REPLACE"),
            ("Add to selection", "ADD"),
            ("Remove from selection", "SUBTRACT")))
        self.assertEqual(selection_combine_summary("subtract"), "Remove from selection")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            selection_combine_summary("toggle")

    def test_elevation_defaults_to_real_source_bounds(self):
        self.assertEqual(recommended_height_range(
            "z_filter", source_bounds={"minz": 894.28, "maxz": 993.31}),
            (894.28, 993.31))
        self.assertEqual(recommended_height_range(
            "z_filter", source_bounds={"min": [1, 2, 3], "max": [4, 5, 9]}),
            (3.0, 9.0))

    def test_profile_limits_beat_broad_source_defaults(self):
        profile = {"vertical_axis": "HeightAboveGround", "vertical_limits": [2, 12]}
        self.assertEqual(recommended_height_range(
            "hag_filter", source_bounds={"minz": 800, "maxz": 1000},
            profile_geometry=profile, display_range=[0, 50]), (2.0, 12.0))

    def test_summary_names_axis_units_view_and_next_selection_scope(self):
        summary = selection_height_summary(
            "hag_filter", [5, 6], view_name="Profile 2")
        for text in ("Profile 2", "Height above ground", "5 to 6",
                     "source height units", "next selection"):
            self.assertIn(text, summary)


if __name__ == "__main__":
    unittest.main()
