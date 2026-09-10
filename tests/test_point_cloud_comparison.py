import unittest

from pyforestscan_qgis.core.point_cloud.comparison import (
    COMPARISON_DISPLAY_ACTIONS, ComparisonSourceRecord,
    comparison_display_command)


class ComparisonContractTests(unittest.TestCase):
    def test_display_commands_are_copied_and_editor_commands_fail_closed(self):
        command = {"action":"mode", "mode":"RGB"}
        result = comparison_display_command(command)
        self.assertEqual(result, command)
        self.assertIsNot(result, command)
        for action in ("selection_tool", "selection_test", "editor_overlay",
                       "measurements", "annotations", "export", "stage"):
            with self.subTest(action=action), self.assertRaisesRegex(
                    ValueError, "display commands only"):
                comparison_display_command({"action":action})
        self.assertIn("resource_limit", COMPARISON_DISPLAY_ACTIONS)

    def test_verified_comparison_identity_is_source_specific(self):
        record = ComparisonSourceRecord.from_viewer_info("ignored.laz", {
            "source_identity":{"path":"comparison.laz", "sha256":"b"*64,
                               "source_type":"LAZ"},
            "point_count":4200,
            "metadata":{"srs":{"authority":"EPSG", "horizontal":6635}},
        }, comparison_id="c"*32)
        self.assertEqual(record.source_fingerprint, "b"*64)
        self.assertEqual(record.source_crs, "EPSG:6635")
        self.assertEqual(record.relationship("a"*64), "INDEPENDENT_SOURCE")
        self.assertEqual(record.relationship("b"*64), "SAME_SOURCE_REFERENCE")
        self.assertEqual(record.authority, "READ_ONLY_INDEPENDENT_SOURCE")

    def test_unverified_or_invalid_comparison_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "verified viewer identity"):
            ComparisonSourceRecord.from_viewer_info("x.laz", {})
        with self.assertRaisesRegex(ValueError, "incomplete or unsafe"):
            ComparisonSourceRecord("c"*32, "x.laz", "not-a-hash", "LAZ")
        with self.assertRaisesRegex(ValueError, "Primary source fingerprint"):
            ComparisonSourceRecord("c"*32, "x.laz", "b"*64, "LAZ").relationship("bad")
