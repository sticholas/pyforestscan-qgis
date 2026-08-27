"""QGIS-free contracts for the productized Tools & Setup page."""

from pathlib import Path
import unittest

from pyforestscan_qgis.ui.ux_summary import processing_engine_setup_action

ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
MISSION = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")


class ToolsSetupProductContractTests(unittest.TestCase):
    def test_processing_engine_action_matrix(self):
        self.assertEqual(processing_engine_setup_action("READY"), (False, "Set Up"))
        self.assertEqual(processing_engine_setup_action("SETUP_REQUIRED"), (True, "Set Up"))
        self.assertEqual(processing_engine_setup_action("REPAIR_REQUIRED"), (True, "Repair"))
        self.assertEqual(processing_engine_setup_action("FAILED"), (True, "Set Up"))
        self.assertEqual(processing_engine_setup_action("INCOMPATIBLE"), (True, "Set Up"))

    def test_additional_tools_and_recent_limit_are_not_visible_controls(self):
        settings = PAGES[PAGES.index("class SettingsPage"):PAGES.index("def _processing_lifecycle_stage")]
        self.assertNotIn('"Additional Tools"', settings)
        self.assertNotIn('"Recent item limit"', settings)
        self.assertNotIn("maximum_recent_items_spin", settings)
        self.assertIn("recent_item_display_limit", settings)
        self.assertIn("never a job limit", settings)

    def test_advanced_settings_are_always_visible(self):
        self.assertIn('defaults = self.add_section("Advanced Settings")', PAGES)
        self.assertNotIn('_collapsible_section(self.content_layout, "Advanced Settings"', PAGES)

    def test_troubleshooting_has_two_purposeful_actions(self):
        settings = PAGES[PAGES.index("class SettingsPage"):PAGES.index("def _processing_lifecycle_stage")]
        self.assertIn('QPushButton("Recheck Processing Engine")', settings)
        self.assertIn('QPushButton("Open Diagnostics")', settings)
        for removed in ("Preview Install Plan", "Verify QGIS Compatibility", "Manual Setup Instructions", "Open Backend Folder", "View Logs"):
            self.assertNotIn(f'QPushButton("{removed}")', settings)

    def test_setup_uses_authoritative_service_and_recheck_does_not_install(self):
        self.assertIn("self.backend_service.processing_engine_service().recheck()", PAGES)
        self.assertIn("self.install_backend_button.clicked.connect(self.install_backend_internal_beta)", PAGES)
        verify = PAGES[PAGES.index("    def verify_backend"):PAGES.index("    def verify_qgis_compatibility")]
        self.assertNotIn("setup_processing_engine", verify)
        self.assertNotIn("install_backend", verify)

    def test_recent_display_bound_does_not_limit_processing(self):
        self.assertIn("self.settings_page.recent_item_display_limit()", MISSION)
        process_source = PAGES[PAGES.index("class BatchPage"):PAGES.index("class ResultsPage")]
        self.assertNotIn("recent_item_display_limit", process_source)


if __name__ == "__main__":
    unittest.main()
