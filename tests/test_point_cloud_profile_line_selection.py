"""Exact original-source Above/Below Line contracts for Vertical Slice."""
from dataclasses import asdict, replace
import importlib.util
import unittest

from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, selection_mask
from pyforestscan_qgis.viewer.editor_worker import visual_definition


def definition(**values):
    profile_axis = values.pop("profile_axis", "Z")
    return SelectionDefinition("line", "session", "a"*64, "LAZ",
        ((0,-1),(10,-1),(10,1),(0,1),(0,-1)), "EPSG:6635",
        profile_a=(0,0), profile_b=(10,0), profile_thickness=2,
        profile_axis=profile_axis, depth_mode="SLICE_CORRIDOR", **values)


class ProfileLineSelectionTests(unittest.TestCase):
    def test_contract_requires_one_finite_nonvertical_line_inside_slice(self):
        valid = definition(profile_line=((2,2),(8,8)), profile_line_side="ABOVE")
        self.assertEqual(valid.profile_line, ((2,2),(8,8)))
        self.assertEqual(SelectionDefinition(**asdict(valid)), valid)
        for values in (
                {"profile_line":((2,2),(2,8)), "profile_line_side":"ABOVE"},
                {"profile_line":((-1,2),(8,8)), "profile_line_side":"ABOVE"},
                {"profile_line":((2,2),(11,8)), "profile_line_side":"BELOW"},
                {"profile_line":((2,2),(8,8)), "profile_line_side":"LEFT"},
                {"profile_line":((2,2),(8,8))},
                {"profile_line_side":"ABOVE"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                definition(**values)
        with self.assertRaisesRegex(ValueError, "Vertical Slice"):
            SelectionDefinition("line", "session", "a"*64, "LAS",
                ((0,0),(10,0),(10,10),(0,10),(0,0)), "EPSG:6635",
                profile_line=((2,2),(8,8)), profile_line_side="ABOVE")

    def test_renderer_projection_retains_authoritative_profile_line(self):
        item = definition(profile_line=((2,2),(8,8)), profile_line_side="BELOW")
        projected = visual_definition(item)
        self.assertEqual(projected["profile_line"], ((2,2),(8,8)))
        self.assertEqual(projected["profile_line_side"], "BELOW")

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed Shapely required")
    def test_above_and_below_are_exact_inclusive_and_direction_independent(self):
        import numpy as np
        points = np.array([
            (2,0,2,20,5), (5,0,4.9,20,5), (5,0,5,20,5), (5,0,5.1,20,5),
            (8,0,8,20,5), (1,0,20,20,5), (9,0,0,20,5), (5,1.01,9,20,5)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("HeightAboveGround","f8"),("Classification","u1")])
        above = definition(profile_line=((2,2),(8,8)), profile_line_side="ABOVE")
        below = replace(above, selection_id="below", profile_line_side="BELOW")
        self.assertEqual(selection_mask(points,[above]).tolist(),
                         [True,False,True,True,True,False,False,False])
        self.assertEqual(selection_mask(points,[below]).tolist(),
                         [True,True,True,False,True,False,False,False])
        reverse = replace(above, profile_line=((8,8),(2,2)))
        self.assertEqual(selection_mask(points,[reverse]).tolist(),
                         selection_mask(points,[above]).tolist())

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed Shapely required")
    def test_hag_class_filters_and_modes_use_existing_sequence_authority(self):
        import numpy as np
        points = np.array([(5,0,100,4,5),(5,0,100,6,5),(5,0,100,6,2),(5,2,100,6,5)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("HeightAboveGround","f8"),("Classification","u1")])
        above = definition(profile_axis="HeightAboveGround",
            profile_line=((2,5),(8,5)), profile_line_side="ABOVE",
            classification_filter=(5,))
        self.assertEqual(selection_mask(points,[above]).tolist(), [False,True,False,False])
        subtract = replace(above, selection_id="subtract", selection_mode="SUBTRACT")
        self.assertFalse(selection_mask(points,[above,subtract]).any())
        add = replace(above, selection_id="add", selection_mode="ADD",
                      profile_line_side="BELOW")
        self.assertEqual(selection_mask(points,[above,add]).tolist(), [True,True,False,False])


if __name__ == "__main__":
    unittest.main()
