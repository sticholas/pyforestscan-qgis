import unittest

from pyforestscan_qgis.core.point_cloud.visualization import (
    DisplayRange, LegendModel, RenderState, available_attribute_modes,
    display_range, histogram, nice_tick_step, nice_ticks, numeric_summary,
    resolve_attribute,
)


class PointCloudVisualizationTests(unittest.TestCase):
    def test_attribute_modes_require_source_dimensions(self):
        modes = available_attribute_modes(("X", "Y", "Z", "Classification", "Intensity"))
        self.assertEqual(("Classification", "Elevation", "Intensity"), modes)

    def test_rgb_requires_all_channels(self):
        self.assertNotIn("RGB", available_attribute_modes(("Red", "Green", "Z")))
        self.assertIn("RGB", available_attribute_modes(("Red", "Green", "Blue")))

    def test_aliased_dimension_satisfies_one_attribute_mode(self):
        modes = available_attribute_modes(("X", "Y", "Z", "ScanAngleRank", "PointSourceID"))
        self.assertIn("Scan Angle", modes)
        self.assertIn("Point Source ID", modes)

    def test_alias_resolution_and_render_state_identity(self):
        self.assertEqual("ScanAngleRank", resolve_attribute("Scan Angle", ("ScanAngleRank",)))
        self.assertIsNone(resolve_attribute("RGB", ("Red", "Green")))
        state = RenderState(color_mode="Elevation", point_size=2)
        self.assertEqual(state.identity(), state.identity())

    def test_bounded_histogram_and_numeric_summary(self):
        result = histogram([0, 1, 2, 3, 4], bins=3)
        self.assertEqual(5, sum(result["bins"]))
        summary = numeric_summary([0, 1, 2, 3, 4])
        self.assertEqual(2.0, summary["median"])
        self.assertEqual(3, summary["p75"])

    def test_nice_ticks_use_readable_intervals(self):
        self.assertIn(nice_tick_step(35), (5.0, 10.0))
        ticks = nice_ticks(12, 18)
        self.assertEqual(ticks, (12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0))

    def test_robust_range_ignores_extreme_values(self):
        result = display_range([0, 1, 2, 3, 4, 1000], mode="ROBUST")
        self.assertLess(result.maximum, 1000)
        self.assertEqual("ROBUST", result.mode)

    def test_manual_range_clamps_values(self):
        result = DisplayRange(0, 10, "MANUAL")
        self.assertEqual(0.0, result.clamp(-3))
        self.assertEqual(10.0, result.clamp(20))

    def test_legend_label_includes_units(self):
        self.assertEqual("Height Above Ground (m)", LegendModel("Height Above Ground", "m").label)


if __name__ == "__main__":
    unittest.main()
