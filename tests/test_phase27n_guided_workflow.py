"""Phase 27N guided polygon workflow tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.core.guided_polygon_workflow import GUIDED_POLYGON_STEPS, PROCESSING_PROFILES, guided_step_indicator, profile_by_key

ROOT = Path(__file__).resolve().parents[1]


class Phase27NGuidedWorkflowTests(unittest.TestCase):
    def test_step_order_matches_guided_polygon_workflow(self) -> None:
        self.assertEqual([step.label for step in GUIDED_POLYGON_STEPS], ["Data", "Area", "Outputs", "Settings", "Review", "Results"])
        self.assertIn("*5 Review*", guided_step_indicator("review"))

    def test_processing_profiles_hide_worker_topology_by_default(self) -> None:
        profiles = {profile.key: profile for profile in PROCESSING_PROFILES}
        self.assertEqual(profiles["conservative"].recommended_workers, 1)
        self.assertEqual(profiles["recommended"].recommended_workers, 2)
        self.assertGreater(profiles["performance"].recommended_workers, profiles["recommended"].recommended_workers)
        self.assertEqual(profile_by_key("missing").key, "recommended")

    def test_batch_page_exposes_guided_actions_and_advanced_profile(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn("guided_review_summary", source)
        self.assertNotIn("polygon_guided_step_label", source)
        self.assertIn("Processing profile", source)
        self.assertIn("Show Selected Files on Map", source)
        self.assertIn("Zoom to Repository Extent", source)
        self.assertIn("Polygon Processing Review", source)
        self.assertIn("Technical Report", source)


if __name__ == "__main__":
    unittest.main()
