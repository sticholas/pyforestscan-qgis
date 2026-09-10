"""QGIS-free source-coordinate linked cursor contracts."""
from dataclasses import asdict
import unittest

from pyforestscan_qgis.core.point_cloud.linked_cursor import (
    linked_cursor_command, linked_cursor_summary, validate_linked_cursor)
from pyforestscan_qgis.core.point_cloud.workspace import (
    AreaGeometry, SliceGeometry, ViewState, ViewType)


class LinkedCursorTests(unittest.TestCase):
    source = "a" * 64

    def cursor(self, **changes):
        payload = dict(sequence=7, active=True, source_xyz=(10, 5, 7),
            display_xyz=(15, 0, 7), height_above_ground=3.5,
            classification=5, authority="ORIGINAL_SOURCE_RECORD_COORDINATES")
        payload.update(changes)
        return validate_linked_cursor(payload, self.source, "profile")

    def test_cursor_is_source_bound_and_fail_closed(self):
        result = self.cursor()
        self.assertEqual(result["source_sha256"], self.source)
        self.assertEqual(result["origin_view_id"], "profile")
        with self.assertRaisesRegex(ValueError, "three finite"):
            self.cursor(source_xyz=(1, 2, float("nan")))
        with self.assertRaisesRegex(ValueError, "authority"):
            self.cursor(authority="RENDERED_POINT_IS_AUTHORITY")
        cleared = validate_linked_cursor(
            {"sequence": 8, "active": False}, self.source, "profile")
        self.assertNotIn("source_xyz", cleared)

    def test_source_record_projects_to_overview_detail_and_path_profile(self):
        overview = ViewState("overview", ViewType.OVERVIEW_3D, "Overview")
        detail = ViewState("detail", ViewType.AREA_DETAIL, "Detail",
            asdict(AreaGeometry("RECTANGLE", "EPSG:32605", (10, 5), 4, 4)))
        profile = ViewState("profile", ViewType.VERTICAL_SLICE, "Profile",
            asdict(SliceGeometry((0, 0), (10, 10), 2, "EPSG:32605",
                path=((0, 0), (10, 0), (10, 10)),
                display_projection="PROFILE_DISTANCE")))
        cursor = self.cursor()
        self.assertEqual(linked_cursor_command(cursor, overview)["display_xyz"],
                         (10, 5, 7))
        self.assertTrue(linked_cursor_command(cursor, detail)["visible"])
        projected = linked_cursor_command(cursor, profile)
        self.assertEqual(projected["display_xyz"], (15, 0, 7))
        self.assertEqual(projected["distance_along"], 15)
        self.assertEqual(projected["source_xyz"], (10, 5, 7))

    def test_cursor_hides_outside_detail_profile_or_vertical_limits(self):
        detail = ViewState("detail", ViewType.AREA_DETAIL, "Detail",
            asdict(AreaGeometry("CIRCLE", "EPSG:32605", (0, 0), radius=1)))
        profile = ViewState("profile", ViewType.VERTICAL_SLICE, "Profile",
            asdict(SliceGeometry((0, 0), (10, 0), 2, "EPSG:32605",
                vertical_limits=(0, 6), display_projection="PROFILE_DISTANCE")))
        self.assertFalse(linked_cursor_command(self.cursor(), detail)["visible"])
        self.assertFalse(linked_cursor_command(self.cursor(), profile)["visible"])
        hag_profile = ViewState("hag", ViewType.VERTICAL_SLICE, "HAG",
            asdict(SliceGeometry((0, 0), (10, 0), 20, "EPSG:32605",
                vertical_axis="HeightAboveGround", display_projection="PROFILE_DISTANCE")))
        self.assertFalse(linked_cursor_command(
            self.cursor(height_above_ground=None), hag_profile)["visible"])

    def test_profile_summary_keeps_words_with_source_coordinates_in_details(self):
        profile = ViewState("profile", ViewType.VERTICAL_SLICE, "Profile",
            asdict(SliceGeometry((0, 0), (10, 10), 2, "EPSG:32605",
                path=((0, 0), (10, 0), (10, 10)),
                display_projection="PROFILE_DISTANCE")))
        summary = linked_cursor_summary(linked_cursor_command(self.cursor(), profile))
        self.assertEqual(summary["text"], "Distance 15.000 | Elevation 7.000")
        for text in ("Source X: 10.000", "Source Y: 5.000", "Source Z: 7.000",
                     "Classification: 5", "Original source-record coordinates"):
            self.assertIn(text, summary["details"])


if __name__ == "__main__":
    unittest.main()
