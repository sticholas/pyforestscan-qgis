"""Exact full-resolution source-Z and HAG-relative sphere contracts."""
from dataclasses import asdict, replace
import importlib.util
import json
import unittest

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, reader_spec, selection_mask, spherical_selection)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.viewer.editor_worker import visual_definition


class SphereContractTests(unittest.TestCase):
    def setUp(self):
        self.base = SelectionDefinition("sphere", "session", "c"*64, "COPC",
            ((0, 0), (2, 0), (2, 2), (0, 0)), "SOURCE_LOCAL:"+"c"*64)
        self.sphere = spherical_selection(self.base, center=(0, 0, 10), radius=2)

    def test_roundtrip_bounded_query_and_overlay(self):
        restored = SelectionDefinition(**json.loads(json.dumps(asdict(self.sphere))))
        self.assertEqual(restored, self.sphere)
        source = SourceIdentity("/source.copc.laz", "c"*64, 1, "COPC")
        self.assertEqual(reader_spec(source, [restored])["bounds"], "([-2,2],[-2,2])")
        visual = visual_definition(restored)
        self.assertEqual(visual["sphere_center"], (0, 0, 10))
        self.assertEqual(visual["sphere_radius"], 2)
        self.assertEqual(visual["sphere_axis"], "Z")

    def test_invalid_incomplete_and_competing_spheres_fail(self):
        for center, radius, axis in (((0, 0), 1, "Z"), ((0, 0, 0), 0, "Z"),
                                     ((0, 0, float("nan")), 1, "Z"),
                                     ((0, 0, 0), 1, "CameraDepth")):
            with self.assertRaises(ValueError):
                spherical_selection(self.base, center=center, radius=radius, axis=axis)
        with self.assertRaisesRegex(ValueError, "sphere-volume"):
            replace(self.sphere, depth_mode="FULL_COLUMN")
        with self.assertRaisesRegex(ValueError, "height axis"):
            replace(self.base, sphere_axis="CameraDepth")
        circle = replace(self.base, geometry=((-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)),
                         circle_center=(0,0), circle_radius=1)
        with self.assertRaisesRegex(ValueError, "competing"):
            spherical_selection(circle, center=(0,0,0), radius=1)

    def test_filters_modes_and_view_identity_are_preserved(self):
        base = replace(self.base, selection_mode="SUBTRACT", z_filter=(2,18),
                       classification_filter=(2,5), view_id="detail")
        sphere = spherical_selection(base, center=(10,20,5), radius=3,
                                     axis="HeightAboveGround")
        for name in ("selection_mode","z_filter","classification_filter","view_id"):
            self.assertEqual(getattr(sphere,name),getattr(base,name))
        self.assertEqual(sphere.depth_mode, "SPHERE_VOLUME")


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("shapely"),
                     "Managed geometry runtime required")
class SphereMembershipTests(SphereContractTests):
    def setUp(self):
        super().setUp()
        import numpy as np
        self.points = np.array([(0,0,10,4,2),(2,0,10,4,5),(0,0,12,6,5),
                                (1.5,1.5,10,4,5),(0,0,13,4,2)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                   ("HeightAboveGround","f8"),("Classification","u1")])

    def test_source_z_boundary_and_xy_envelope_corner(self):
        self.assertEqual(selection_mask(self.points,[self.sphere]).tolist(),
                         [True,True,True,False,False])

    def test_hag_relative_sphere_and_existing_filters_intersect(self):
        sphere = spherical_selection(self.base, center=(0,0,4), radius=2,
                                     axis="HeightAboveGround")
        sphere = replace(sphere, classification_filter=(5,))
        self.assertEqual(selection_mask(self.points,[sphere]).tolist(),
                         [False,True,True,False,False])

    def test_missing_hag_fails_clearly(self):
        import numpy as np
        points=np.array([(0,0,4)],dtype=[("X","f8"),("Y","f8"),("Z","f8")])
        sphere=spherical_selection(self.base,center=(0,0,4),radius=1,
                                   axis="HeightAboveGround")
        with self.assertRaisesRegex(ValueError,"HeightAboveGround"):
            selection_mask(points,[sphere])

    def test_add_subtract_and_journal_replay_use_exact_sphere(self):
        import numpy as np
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        from pyforestscan_qgis.core.point_cloud.session import AttributeEditOperation
        subtract=replace(self.sphere,selection_id="subtract",selection_mode="SUBTRACT",
                         classification_filter=(5,))
        self.assertEqual(selection_mask(self.points,[self.sphere,subtract]).tolist(),
                         [True,False,False,False,False])
        original=self.points.copy()
        operation=AttributeEditOperation("edit","now",(self.sphere,),"Classification",9,3)
        actual,_=EditExecutionPlan((operation,)).apply(self.points)
        np.testing.assert_array_equal(self.points,original)
        self.assertEqual(actual["Classification"].tolist(),[9,9,9,5,2])


if __name__ == "__main__":
    unittest.main()
