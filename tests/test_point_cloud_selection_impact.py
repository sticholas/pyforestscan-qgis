"""Selection impact is visible early and enforced by one shared policy."""
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.selection_impact import (
    selection_impact, selection_impact_suffix)


class SelectionImpactTests(unittest.TestCase):
    def test_routine_and_empty_selections_have_no_warning(self):
        self.assertEqual(selection_impact(0, 100).level, "EMPTY")
        self.assertEqual(selection_impact_suffix(100, 10_000), "")

    def test_review_tier_is_advisory(self):
        impact = selection_impact(1_000_001, 20_000_000)
        self.assertEqual(impact.level, "REVIEW")
        self.assertFalse(impact.requires_confirmation)
        self.assertIn("review", selection_impact_suffix(1_000_001, 20_000_000))
        self.assertEqual(selection_impact(101, 1000).level, "REVIEW")

    def test_existing_very_large_threshold_requires_confirmation(self):
        for count, total in ((10_000_001, 100_000_000), (251, 1000)):
            impact = selection_impact(count, total)
            self.assertEqual(impact.level, "CONFIRM")
            self.assertTrue(impact.requires_confirmation)
            self.assertIn("confirmation required", impact.message)
        self.assertFalse(selection_impact(10_000_000, 100_000_000).requires_confirmation)
        self.assertFalse(selection_impact(250, 1000).requires_confirmation)

    def test_invalid_counts_fail_closed(self):
        for selected, total in ((-1,10),(11,10),(1,0),(True,10),(1,1.5)):
            with self.assertRaises(ValueError):
                selection_impact(selected,total)

    def test_worker_and_both_ui_surfaces_use_shared_policy(self):
        root = Path(__file__).resolve().parents[1] / "pyforestscan_qgis"
        worker = (root / "viewer/editor_worker.py").read_text()
        docked = (root / "ui/point_cloud_editor.py").read_text()
        detached = (root / "ui/point_cloud_detached.py").read_text()
        self.assertIn("impact = selection_impact(", worker)
        self.assertNotIn("result.resolved_point_count > 10_000_000", worker)
        self.assertIn("selection_impact_suffix", docked)
        self.assertIn("selection_impact_suffix", detached)


if __name__ == "__main__":
    unittest.main()
