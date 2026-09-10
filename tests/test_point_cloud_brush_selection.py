"""Authoritative round-capped source-space brush corridor contracts."""
from dataclasses import asdict, replace
import importlib.util
import json
import unittest

from pyforestscan_qgis.core.point_cloud.selection import (
    SelectionDefinition, brush_selection, reader_spec, selection_mask)
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.viewer.editor_worker import visual_definition


class BrushContractTests(unittest.TestCase):
    def setUp(self):
        self.base = SelectionDefinition("brush", "session", "b"*64, "COPC",
            ((0, 0), (2, 0), (2, 2), (0, 0)), "SOURCE_LOCAL:"+"b"*64)
        self.brush = brush_selection(self.base, path=((0, 0), (4, 0), (4, 4)), radius=1)

    def test_roundtrip_bounded_query_and_overlay(self):
        restored = SelectionDefinition(**json.loads(json.dumps(asdict(self.brush))))
        self.assertEqual(restored, self.brush)
        source = SourceIdentity("/source.copc.laz", "b"*64, 1, "COPC")
        self.assertEqual(reader_spec(source, [restored])["bounds"], "([-1,5],[-1,5])")
        visual = visual_definition(restored)
        self.assertEqual(visual["brush_path"], ((0, 0), (4, 0), (4, 4)))
        self.assertEqual(visual["brush_radius"], 1)
        self.assertEqual(visual["brush_tolerance"], 0)

    def test_invalid_and_competing_primitives_fail(self):
        for path, radius in (((), 1), (((0, 0), (0, 0)), 1),
                             (((0, float("nan")),), 1), (((0, 0),), 0)):
            with self.assertRaises(ValueError):
                brush_selection(self.base, path=path, radius=radius)
        for tolerance in (-1, .251, float("nan")):
            with self.assertRaises(ValueError):
                brush_selection(self.base, path=((0,0),(1,0)), radius=1,
                                tolerance=tolerance)
        circle = replace(self.base, geometry=((-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)),
                         circle_center=(0,0), circle_radius=1)
        with self.assertRaisesRegex(ValueError, "competing"):
            brush_selection(circle, path=((0,0),(1,0)), radius=1)

    def test_constraints_and_modes_are_preserved(self):
        base = replace(self.base, selection_mode="SUBTRACT", z_filter=(2,8),
                       classification_filter=(2,5), depth_mode="CUSTOM_DEPTH_RANGE")
        brush = brush_selection(base, path=((10,10),(20,20)), radius=2)
        for name in ("selection_mode","z_filter","classification_filter","depth_mode"):
            self.assertEqual(getattr(brush,name),getattr(base,name))


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("shapely"),
                     "Managed geometry runtime required")
class BrushMembershipTests(BrushContractTests):
    def test_segment_endpoint_corner_and_turn_membership(self):
        import numpy as np
        points=np.array([(-1,0,3),(2,.75,3),(4.75,2,3),(5,5,3),(2,1.01,3)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8")])
        self.assertEqual(selection_mask(points,[self.brush]).tolist(),
                         [True,True,True,False,False])

    def test_height_constraint_intersects_brush(self):
        import numpy as np
        points=np.array([(2,0,2,1),(2,0,8,7),(2,0,9,2)],
            dtype=[("X","f8"),("Y","f8"),("Z","f8"),("HeightAboveGround","f8")])
        brush=replace(self.brush,z_filter=(2,8),hag_filter=(1,2),
                      depth_mode="CUSTOM_DEPTH_RANGE")
        self.assertEqual(selection_mask(points,[brush]).tolist(),[True,False,False])
