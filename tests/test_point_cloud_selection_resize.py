"""Managed geometry contracts for source-space Grow/Shrink Selection."""
from dataclasses import replace
import importlib.util
import unittest

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, brush_selection, circular_selection, resized_selection,
    spherical_selection)


class ResizeSelectionContractTests(unittest.TestCase):
    def setUp(self):
        self.base = SelectionDefinition("base", "session", "a"*64, "LAZ",
            ((0,0),(10,0),(10,10),(0,10),(0,0)), "EPSG:6635")

    def test_exact_primitives_resize_in_source_units(self):
        circle = circular_selection(self.base, center=(5,5), radius=3)
        self.assertEqual(resized_selection([circle], 2, selection_id="grown")[0].circle_radius, 5)
        brush = brush_selection(self.base, path=((0,0),(10,0)), radius=2)
        self.assertEqual(resized_selection([brush], -1)[0].brush_radius, 1)
        sphere = spherical_selection(self.base, center=(5,5,12), radius=4,
                                     axis="HeightAboveGround")
        resized = resized_selection([sphere], 1)[0]
        self.assertEqual((resized.sphere_radius, resized.sphere_axis),
                         (5, "HeightAboveGround"))

    def test_unsupported_or_destructive_resize_fails_closed(self):
        for distance in (0, float("inf"), True):
            with self.assertRaises(ValueError):
                resized_selection([self.base], distance)
        with self.assertRaises(ValueError):
            resized_selection([replace(self.base, invert_result=True)], 1)
        added = replace(self.base, selection_id="add", selection_mode="ADD")
        with self.assertRaises(ValueError):
            resized_selection([self.base, added], 1)
        circle = circular_selection(self.base, center=(5,5), radius=3)
        with self.assertRaises(ValueError):
            resized_selection([circle], -3)

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed geometry runtime required")
    def test_polygon_growth_and_shrink_preserve_single_closed_geometry(self):
        grown = resized_selection([self.base], 2)[0]
        shrunk = resized_selection([self.base], -2)[0]
        self.assertEqual(grown.geometry[0], grown.geometry[-1])
        self.assertEqual(shrunk.geometry[0], shrunk.geometry[-1])
        self.assertLess(min(x for x,_y in grown.geometry), 0)
        self.assertEqual((min(x for x,_y in shrunk.geometry),
                          max(x for x,_y in shrunk.geometry)), (2,8))
        with self.assertRaisesRegex(ValueError, "remove or split"):
            resized_selection([self.base], -6)


if __name__ == "__main__":
    unittest.main()
