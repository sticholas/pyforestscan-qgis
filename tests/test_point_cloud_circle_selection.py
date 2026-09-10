"""Exact full-resolution circle/cylinder membership and existing journal replay."""
from dataclasses import asdict, replace
import importlib.util
import json
import unittest

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, circular_selection, reader_spec, selection_mask)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.viewer.editor_worker import visual_definition


class CircleContractTests(unittest.TestCase):
    def setUp(self):
        self.base = SelectionDefinition("circle", "session", "a"*64, "COPC",
            ((0, 0), (2, 0), (2, 2), (0, 0)), "SOURCE_LOCAL:"+"a"*64)
        self.circle = circular_selection(self.base, center=(0, 0), radius=1)

    def test_roundtrip_and_bounded_full_resolution_reader(self):
        restored = SelectionDefinition(**json.loads(json.dumps(asdict(self.circle))))
        self.assertEqual(restored, self.circle)
        source = SourceIdentity("/source.copc.laz", "a"*64, 1, "COPC")
        spec = reader_spec(source, [restored])
        self.assertEqual(spec["bounds"], "([-1,1],[-1,1])")
        self.assertFalse({"resolution", "depth", "count"} & spec.keys())

    def test_invalid_radius_center_and_incomplete_contract(self):
        for radius in (0, -1, True, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                circular_selection(self.base, center=(0, 0), radius=radius)
        with self.assertRaises(ValueError):
            circular_selection(self.base, center=(float("inf"), 0), radius=1)
        with self.assertRaises(ValueError):
            replace(self.base, circle_center=(0, 0))

    def test_undersized_query_envelope_rejected(self):
        with self.assertRaisesRegex(ValueError, "envelope"):
            replace(self.circle, geometry=self.base.geometry)

    def test_constraints_and_view_identity_preserved(self):
        base = replace(self.base, z_filter=(2, 8), hag_filter=(1, 6),
            classification_filter=(2, 5), view_id="detail", depth_mode="CUSTOM_DEPTH_RANGE")
        circle = circular_selection(base, center=(100, 200), radius=3)
        for field in ("z_filter", "hag_filter", "classification_filter", "view_id", "depth_mode"):
            self.assertEqual(getattr(circle, field), getattr(base, field))

    def test_renderer_overlay_retains_exact_circle_predicate(self):
        visual = visual_definition(self.circle)
        self.assertEqual(visual["circle_center"], (0, 0))
        self.assertEqual(visual["circle_radius"], 1)
        self.assertEqual(set(visual), {"geometry", "selection_mode", "z_filter", "hag_filter",
            "classification_filter", "attribute_filters", "view_id", "view_name", "clip_geometry",
            "profile_a", "profile_b", "profile_path", "profile_thickness", "profile_geometry", "profile_axis",
            "depth_mode", "circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
            "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
            "sphere_center", "sphere_radius", "sphere_axis", "invert_result",
            "profile_line", "profile_line_side"})


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("shapely"),
                     "Managed geometry runtime required")
class CircleMembershipTests(CircleContractTests):
    def setUp(self):
        super().setUp()
        import numpy as np
        self.points = np.array([(0, 0, 2, 1, 2), (1, 0, 3, 2, 5),
            (0, -1, 8, 6, 5), (.9, .9, 3, 2, 5), (0, 0, 20, 19, 2)],
            dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"),
                   ("HeightAboveGround", "f8"), ("Classification", "u1")])

    def test_circle_boundary_included_and_envelope_corner_excluded(self):
        self.assertEqual(selection_mask(self.points, [self.circle]).tolist(),
                         [True, True, True, False, True])

    def test_cylinder_height_hag_and_class_intersection(self):
        cylinder = replace(self.circle, z_filter=(2, 8), hag_filter=(1, 2),
                           classification_filter=(5,), depth_mode="CUSTOM_DEPTH_RANGE")
        self.assertEqual(selection_mask(self.points, [cylinder]).tolist(),
                         [False, True, False, False, False])

    def test_add_subtract_uses_same_membership(self):
        subtract = replace(self.circle, selection_id="subtract", selection_mode="SUBTRACT",
                           z_filter=(2, 3))
        self.assertEqual(selection_mask(self.points, [self.circle, subtract]).tolist(),
                         [False, False, True, False, True])
        add = replace(subtract, selection_id="add", selection_mode="ADD")
        self.assertEqual(selection_mask(self.points, [self.circle, subtract, add]).tolist(),
                         [True, True, True, False, True])

    def test_journal_replay_preserves_original_and_ignores_envelope_corners(self):
        import numpy as np
        from pyforestscan_qgis.core.point_cloud.session import AttributeEditOperation
        from pyforestscan_qgis.core.point_cloud.edit_plan import EditExecutionPlan
        original = self.points.copy()
        op = AttributeEditOperation("edit", "now", (self.circle,), "Classification", 9, 4)
        restored = AttributeEditOperation("edit", "now",
            (SelectionDefinition(**json.loads(json.dumps(asdict(self.circle)))),),
            "Classification", 9, 4)
        expected, _ = EditExecutionPlan((op,)).apply(self.points)
        actual, removed = EditExecutionPlan((restored,)).apply(self.points)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(self.points, original)
        self.assertEqual(actual["Classification"].tolist(), [9, 9, 9, 5, 9])
        self.assertFalse(removed.any())
