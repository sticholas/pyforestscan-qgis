"""Authoritative multi-segment profile geometry, selection and measurement."""
from dataclasses import asdict
import importlib.util
import unittest

import numpy as np

from pyforestscan_qgis.core.point_cloud.measurement import resolve_profile_anchor_chunks
from pyforestscan_qgis.core.point_cloud.profile import (
    profile_coordinates, profile_membership, profile_query_envelopes)
from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, reader_spec, selection_mask)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.core.point_cloud.workspace import SliceGeometry


class MultiSegmentProfileTests(unittest.TestCase):
    def profile(self, **values):
        options = dict(a=(0, 0), b=(10, 10), thickness=2, crs="EPSG:32605",
                       path=((0, 0), (10, 0), (10, 10)),
                       display_projection="PROFILE_DISTANCE")
        options.update(values)
        return SliceGeometry(**options)

    def test_cumulative_projection_and_validation(self):
        profile = self.profile()
        self.assertEqual(profile.length, 20)
        self.assertEqual(profile.local(10, 5, 7), (15, 7, 0))
        along, cross, _ = profile_coordinates(profile, [5, 10], [1, 5], np)
        np.testing.assert_allclose(along, [5, 15])
        np.testing.assert_allclose(cross, [1, 0])
        with self.assertRaisesRegex(ValueError, "matching its endpoints"):
            self.profile(path=((1, 0), (10, 0), (10, 10)))
        with self.assertRaisesRegex(ValueError, "distinct consecutive"):
            self.profile(path=((0, 0), (10, 0), (10, 0), (10, 10)))

    def test_flat_ends_and_round_join_membership(self):
        profile = self.profile()
        inside = profile_membership(profile,
            np.array([5, 11, -0.1, 10, 10.7]),
            np.array([1, 5, 0, -0.7, 10.7]), np)
        self.assertEqual(inside.tolist(), [True, True, False, True, False])
        self.assertEqual(profile_query_envelopes(profile),
                         ((-1, -1, 11, 1), (9, -1, 11, 11)))

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed Shapely required")
    def test_authoritative_selection_uses_each_path_segment(self):
        points = np.array([(5, 0, 3, 5), (10, 5, 7, 2), (5, 5, 4, 5),
                           (-.5, 0, 2, 5), (10, 10.5, 9, 5)],
                          dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"),
                                 ("Classification", "u1")])
        profile = self.profile()
        definition = SelectionDefinition(
            "path", "session", "a"*64, "LAS", profile.corridor(), "EPSG:32605",
            profile_a=profile.a, profile_b=profile.b, profile_path=profile.points,
            profile_thickness=profile.thickness,
            profile_geometry=((0, 0), (20, 0), (20, 8), (0, 8), (0, 0)),
            depth_mode="SLICE_CORRIDOR")
        self.assertEqual(selection_mask(points, (definition,)).tolist(),
                         [True, True, False, False, False])
        restored = SelectionDefinition(**asdict(definition))
        self.assertEqual(restored.profile_path, profile.points)
        source = SourceIdentity("/source.copc.laz", "a"*64, 5, "COPC")
        reader = reader_spec(source, (restored,))
        self.assertEqual(reader["type"], "readers.copc")
        self.assertIn("POLYGON", reader["polygon"][0])
        self.assertNotIn("resolution", reader)

    def test_projected_profile_measurement_resolves_original_points(self):
        points = np.array([(5, 0, 3, 5), (10, 5, 7, 2)],
                          dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"),
                                 ("Classification", "u1")])
        anchors, _duration = resolve_profile_anchor_chunks(
            (points,), 2, ((5, 0, 3), (15, 0, 7)), self.profile())
        self.assertEqual(anchors[0].source_xyz, (5, 0, 3))
        self.assertEqual(anchors[1].source_xyz, (10, 5, 7))
        self.assertEqual(anchors[1].display_xyz, (15, 0, 7))
        self.assertEqual(anchors[1].profile_position, (15, 7))


if __name__ == "__main__":
    unittest.main()
