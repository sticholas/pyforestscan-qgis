"""QGIS-free profile workbench contracts."""
import unittest

from dataclasses import asdict

from pyforestscan_qgis.core.point_cloud.profile import (
    profile_footprint_command, profile_workbench_summary)
from pyforestscan_qgis.core.point_cloud.workspace import (
    PointCloudWorkspaceModel, SliceGeometry, ViewType)


class ProfileWorkbenchTests(unittest.TestCase):
    def geometry(self, **values):
        result = {"a": (0, 0), "b": (10, 0), "thickness": 4,
                  "crs": "EPSG:32605", "vertical_axis": "Z"}
        result.update(values)
        return result

    def test_summary_names_axes_width_and_authoritative_count(self):
        summary = profile_workbench_summary(self.geometry(), {
            "source_points": 12345, "display_points": 4000,
            "classification_counts": [(5, 9000), (2, 3345)],
        })
        self.assertEqual(summary["text"],
            "12,345 points | X distance | Y elevation | 4 XY wide")
        self.assertIn("Authoritative source points in corridor: 12,345", summary["details"])
        self.assertIn("High vegetation: 9,000", summary["details"])
        self.assertIn("displayed samples are not edit authority", summary["details"])

    def test_hag_and_loading_states_are_explicit(self):
        summary = profile_workbench_summary(
            self.geometry(vertical_axis="HeightAboveGround"))
        self.assertIn("Y HAG", summary["text"])
        self.assertIn("Loading points", summary["text"])

    def test_invalid_profile_geometry_fails_closed(self):
        with self.assertRaises(ValueError):
            profile_workbench_summary(self.geometry(thickness=0))

    def test_profile_footprints_are_bounded_source_space_context(self):
        model = PointCloudWorkspaceModel()
        model.register(view_id="overview")
        first = model.register(ViewType.VERTICAL_SLICE, "Profile 1", view_id="p1",
            geometry=asdict(SliceGeometry((0,0),(10,0),4,"EPSG:32605")))
        model.register(ViewType.VERTICAL_SLICE, "Profile 2", view_id="p2",
            geometry=asdict(SliceGeometry((0,0),(0,10),2,"EPSG:32605")))
        model.activate(first)
        command = profile_footprint_command(
            model.views, active_view_id=model.active_view_id)
        self.assertEqual(command["action"], "workspace_views")
        self.assertEqual([item["view_id"] for item in command["profiles"]], ["p1", "p2"])
        self.assertTrue(command["profiles"][0]["active"])
        self.assertEqual(command["profiles"][0]["corridor"],
                         ((0,2),(10,2),(10,-2),(0,-2),(0,2)))

    def test_profile_footprint_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            profile_footprint_command((), limit=0)


if __name__ == "__main__":
    unittest.main()
