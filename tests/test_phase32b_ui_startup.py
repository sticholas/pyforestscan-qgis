"""QGIS-free contracts for resilient Mission Control startup."""

from pathlib import Path
import unittest

from pyforestscan_qgis.ui.availability import ApplicationAvailability, UiInitializationState

ROOT = Path(__file__).resolve().parents[1]
MISSION = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
PLUGIN = (ROOT / "pyforestscan_qgis/plugin.py").read_text(encoding="utf-8")


class UiStartupResilienceTests(unittest.TestCase):
    def test_application_and_processing_availability_are_independent(self):
        availability = ApplicationAvailability()
        self.assertTrue(availability.ui_available)
        self.assertFalse(availability.processing_available)
        self.assertEqual(availability.engine_status, "CHECKING")

    def test_lifecycle_contract(self):
        self.assertEqual(
            tuple(item.value for item in UiInitializationState),
            ("CREATING", "READY", "DESTROYING"),
        )

    def test_removed_smart_status_widget_has_no_producer_or_consumer(self):
        self.assertNotIn("smart_system_status_label", PAGES)
        self.assertNotIn("smart_system_status_label", MISSION)

    def test_status_bar_uses_semantic_page_api_and_cached_availability(self):
        method = MISSION[MISSION.index("    def _update_status_bar"):MISSION.index("    def _open_documentation")]
        self.assertIn("self.batch_page.set_smart_status", method)
        self.assertIn("self.application_availability", method)
        self.assertNotIn("processing_engine_state(", method)
        self.assertNotIn("smart_status_label", method)

    def test_settings_constructor_does_not_verify_engine(self):
        constructor = PAGES[PAGES.index("class SettingsPage"):PAGES.index("    def set_workspace_session")]
        self.assertIn("self.set_processing_engine_state(None)", constructor)
        self.assertNotIn("self.refresh_backend_summary()", constructor)
        self.assertNotIn("backend_service.processing_engine_state(", constructor)

    def test_engine_resolution_is_deferred_until_ui_ready(self):
        self.assertIn("self._ui_lifecycle = UiInitializationState.READY", MISSION)
        self.assertIn("QTimer.singleShot(0, self._resolve_processing_engine_state)", MISSION)
        self.assertIn("if self._ui_lifecycle is not UiInitializationState.READY", MISSION)

    def test_engine_failure_is_contained(self):
        resolver = MISSION[MISSION.index("    def _resolve_processing_engine_state"):MISSION.index("    def _load_workspace_session")]
        self.assertIn("ApplicationAvailability.unavailable", resolver)
        self.assertIn("Processing Engine status unavailable", resolver)

    def test_semantic_page_contracts_exist(self):
        self.assertIn("def set_processing_engine_state(self, engine", PAGES)
        self.assertIn("def set_smart_status(self, headline", PAGES)
        self.assertNotIn("settings_page.smart_", MISSION)
        self.assertNotIn("batch_page.smart_status_label", MISSION)

    def test_plugin_unload_rejects_late_engine_events(self):
        self.assertIn("self.mission_control.prepare_for_unload()", PLUGIN)
        self.assertIn("UiInitializationState.DESTROYING", MISSION)

    def test_init_gui_has_no_setup_or_scientific_runtime_calls(self):
        init_gui = PLUGIN[PLUGIN.index("    def initGui"):PLUGIN.index("    def unload")]
        for forbidden in ("setup_processing_engine", "install_backend", "import pyforestscan", "import pdal", "import rasterio"):
            self.assertNotIn(forbidden, init_gui.lower())

    def test_qgis_smoke_exercises_exact_regression(self):
        smoke = (ROOT / "scripts/qgis_ui_startup_smoke.py").read_text(encoding="utf-8")
        self.assertIn("dock._update_status_bar()", smoke)
        self.assertIn("plugin._show_mission_control()", smoke)
        self.assertIn("range(100)", smoke)
        self.assertIn("new_scientific_imports", smoke)


if __name__ == "__main__":
    unittest.main()
