"""Phase 32Y scientific readability, state ownership, and guidance contracts."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.ui.ux_summary import (
    next_processing_action,
    processing_area_summary,
    processing_engine_setup_action,
    scientific_form_column_count,
)


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class Phase32YReleaseHardeningTests(unittest.TestCase):
    def test_scientific_form_is_readable_and_responsive(self) -> None:
        self.assertEqual(1, scientific_form_column_count(759))
        self.assertEqual(2, scientific_form_column_count(760))
        self.assertIn("product_settings_secondary_form", PAGES)
        self.assertIn('("Shared settings", "Grid resolution"', PAGES)
        self.assertIn("setVerticalSpacing(max(SPACING_SM", PAGES)

    def test_initial_processing_area_is_explicitly_unselected(self) -> None:
        summary = processing_area_summary()
        self.assertIn("Area: Not selected", summary)
        self.assertIn("Processing Area CRS: Not selected", summary)
        self.assertNotIn("EPSG:4326", summary)
        self.assertIn("self._adopted_polygon_selection", PAGES)

    def test_area_summary_never_converts_unknown_raw_area(self) -> None:
        summary = processing_area_summary(feature_count=2, area_hectares=None, crs="EPSG:4326", adopted=True)
        self.assertIn("Area: Unavailable", summary)
        self.assertNotIn("0.000", summary)
        self.assertIn("float(hectares) * 10000.0", PAGES)
        self.assertNotIn("area = float(polygon.area)", PAGES)

    def test_one_next_action_is_derived_from_readiness(self) -> None:
        self.assertEqual("Install or repair the Processing Engine", next_processing_action(engine_ready=False, source_ready=False, area_required=False, area_ready=False, prerun_ready=False))
        self.assertEqual("Choose LiDAR data", next_processing_action(engine_ready=True, source_ready=False, area_required=False, area_ready=False, prerun_ready=False))
        self.assertEqual("Choose and adopt a processing area", next_processing_action(engine_ready=True, source_ready=True, area_required=True, area_ready=False, prerun_ready=False))
        self.assertEqual("Run Prerun Check", next_processing_action(engine_ready=True, source_ready=True, area_required=True, area_ready=True, prerun_ready=False))
        self.assertEqual("Process LiDAR", next_processing_action(engine_ready=True, source_ready=True, area_required=True, area_ready=True, prerun_ready=True))

    def test_engine_actions_are_state_specific(self) -> None:
        self.assertEqual((True, "Install Processing Engine"), processing_engine_setup_action("SETUP_REQUIRED"))
        self.assertEqual((True, "Reinstall / Repair"), processing_engine_setup_action("READY"))
        self.assertEqual((True, "Repair Processing Engine"), processing_engine_setup_action("REPAIR_REQUIRED"))
        self.assertEqual((True, "Update Processing Engine"), processing_engine_setup_action("INCOMPATIBLE"))

    def test_fallback_crs_precedes_startup(self) -> None:
        output = PAGES.index('form.addRow("Default output folder"')
        fallback = PAGES.index('form.addRow("Fallback CRS"')
        startup = PAGES.index('form.addRow("Startup"')
        self.assertLess(output, fallback)
        self.assertLess(fallback, startup)


if __name__ == "__main__":
    unittest.main()
