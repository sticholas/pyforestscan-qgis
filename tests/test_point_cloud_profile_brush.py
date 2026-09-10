"""Authoritative brush selection in distance/elevation or HAG profile space."""
from dataclasses import asdict, replace
import importlib.util
import json
import unittest

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, reader_spec, selection_mask)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry
from pyforestscan_qgis.viewer.editor_worker import visual_definition
from scripts.testing.pbm_point_cloud_profile_brush_smoke import (
    coordinate_pairs, round_brush_mask)


class ProfileBrushContractTests(unittest.TestCase):
    def test_real_source_canary_helpers_reject_ambiguous_coordinates(self):
        self.assertEqual(coordinate_pairs((1, 2, 3, 4), "Path"),
                         ((1, 2), (3, 4)))
        for values in ((), (1, 2), (1, 2, 3)):
            with self.assertRaisesRegex(ValueError, "at least two"):
                coordinate_pairs(values, "Path")

    def profile(self, **values):
        options = dict(a=(0, 0), b=(10, 10), thickness=2, crs="EPSG:32605",
                       path=((0, 0), (10, 0), (10, 10)),
                       display_projection="PROFILE_DISTANCE")
        options.update(values)
        return SliceGeometry(**options)

    def definition(self, **values):
        profile = self.profile()
        options = dict(profile_a=profile.a, profile_b=profile.b,
            profile_path=profile.points, profile_thickness=profile.thickness,
            profile_axis="Z", depth_mode="SLICE_CORRIDOR",
            profile_brush_path=((4, 4), (16, 8)), profile_brush_radius=1)
        options.update(values)
        return SelectionDefinition("profile-brush", "session", "a"*64, "COPC",
            profile.corridor(), profile.crs, **options)

    def test_roundtrip_and_renderer_keep_exact_profile_stroke(self):
        item = self.definition(profile_brush_tolerance=.2)
        restored = SelectionDefinition(**json.loads(json.dumps(asdict(item))))
        self.assertEqual(restored, item)
        visual = visual_definition(restored)
        self.assertEqual(visual["profile_brush_path"], ((4, 4), (16, 8)))
        self.assertEqual(visual["profile_brush_radius"], 1)
        self.assertEqual(visual["profile_brush_tolerance"], .2)

    def test_invalid_or_competing_profile_strokes_fail_closed(self):
        for changes in (
                {"profile_brush_path": ((-1, 4),)},
                {"profile_brush_path": ((21, 4),)},
                {"profile_brush_path": ((4, 4), (4, 4))},
                {"profile_brush_radius": 0},
                {"profile_brush_tolerance": .3},
                {"profile_geometry": ((0,0),(1,0),(1,1),(0,0))}):
            with self.assertRaises(ValueError):
                self.definition(**changes)
        with self.assertRaisesRegex(ValueError, "Vertical Slice"):
            SelectionDefinition("bad", "session", "a"*64, "LAS",
                ((0,0),(1,0),(1,1),(0,0)), "EPSG:32605",
                profile_brush_path=((0,0),), profile_brush_radius=1)
        with self.assertRaisesRegex(ValueError, "competing"):
            replace(self.definition(), brush_path=((0,0),), brush_radius=1)


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("shapely"),
                     "Managed geometry runtime required")
class ProfileBrushMembershipTests(ProfileBrushContractTests):
    def test_independent_canary_round_brush_has_round_caps(self):
        import numpy as np
        x = np.array((-1, 0, 5, 10, 11, 5))
        y = np.array((0, 1, 1, -1, 0, 1.01))
        self.assertEqual(
            round_brush_mask(x, y, ((0, 0), (10, 0)), 1, np).tolist(),
            [True, True, True, True, True, False])

    def test_copc_reader_is_bounded_to_the_source_profile_corridor(self):
        source = SourceIdentity("/source.copc.laz", "a"*64, 1, "COPC")
        spec = reader_spec(source, (self.definition(),))
        self.assertEqual(spec["type"], "readers.copc")
        self.assertIn("polygon", spec)

    def test_multisegment_distance_elevation_membership_uses_original_records(self):
        import numpy as np
        points = np.array([
            (4, 0, 4, 2, 5),
            (10, 6, 8, 4, 5),
            (10, 6, 10, 6, 5),
            (4, 1.01, 4, 2, 5),
            (7, 0, 7, 5, 5),
        ], dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                  ("HeightAboveGround","f8"),("Classification","u1")])
        self.assertEqual(selection_mask(points, (self.definition(),)).tolist(),
                         [True, True, False, False, False])

    def test_hag_axis_and_add_subtract_reuse_the_same_authority(self):
        import numpy as np
        points = np.array([(4,0,100,4),(10,6,200,8),(10,6,8,30)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),("HeightAboveGround","f8")])
        item = self.definition(profile_axis="HeightAboveGround")
        self.assertEqual(selection_mask(points, (item,)).tolist(), [True,True,False])
        subtract = replace(item, selection_id="subtract", selection_mode="SUBTRACT",
                           profile_brush_path=((16,8),))
        self.assertEqual(selection_mask(points, (item, subtract)).tolist(),
                         [True,False,False])


if __name__ == "__main__":
    unittest.main()
