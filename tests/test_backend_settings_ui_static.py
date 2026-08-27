"""Static tests for Phase 22B Mission Control Settings PBM controls."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BackendSettingsUiStaticTests(unittest.TestCase):
    """Audit Settings-page PBM controls without importing QGIS."""

    def test_install_button_uses_internal_beta_availability(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('self.install_backend_button = QPushButton("Set Up Processing Engine")', source)
        self.assertIn('"Repair / Reload Processing Engine"', source)
        self.assertIn("processing_engine_setup_action", source)
        self.assertIn("self.install_backend_button.clicked.connect(self.install_backend_internal_beta)", source)
        self.assertIn("This will set up all PyForestScan processing components in your user-local PyForestScan folder", source)
        self.assertIn("It will not modify QGIS or system Python", source)

    def test_install_plan_and_compatibility_are_consolidated_into_diagnostics(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertNotIn('QPushButton("Preview Install Plan")', source)
        self.assertNotIn('QPushButton("Verify QGIS Compatibility")', source)
        self.assertIn("preview_install_plan", source)
        self.assertIn("verify_qgis_compatibility", source)
        self.assertIn('QPushButton("Open Diagnostics")', source)

    def test_release_readiness_and_manual_setup_guidance_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertNotIn('QPushButton("Manual Setup Instructions")', source)
        self.assertIn("Plugin ZIP", source)
        self.assertIn("Backend installer", source)
        self.assertIn("Manual setup", source)
        self.assertIn("open_processing_engine_diagnostics", source)

    def test_backend_install_progress_ui_and_worker_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("class _BackendInstallWorker(QObject)", source)
        self.assertIn("progressUpdated = pyqtSignal(object)", source)
        self.assertIn("self.backend_install_progress_bar", source)
        self.assertIn("Stage:", source)
        self.assertIn("Current step:", source)
        self.assertIn("Elapsed time:", source)
        self.assertIn("Latest message:", source)
        self.assertIn("Step progress is estimated.", source)
        self.assertIn('QGroupBox("Technical log")', source)

    def test_install_running_state_disables_backend_action_buttons(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("def _set_backend_install_running", source)
        self.assertIn("for button in self._backend_install_action_buttons():", source)
        self.assertIn("button.setEnabled(not running)", source)
        self.assertIn("self.backend_install_thread = QThread(self)", source)
        self.assertIn("Installation is running. Please wait for this step to finish.", source)
        self.assertNotIn('QPushButton("Cancel Backend Install")', source)

    def test_environment_page_status_uses_report_readiness(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("_set_status_badge(self.status_label, report.readiness.value", source)
        self.assertIn("self.environmentChanged.emit(report.readiness.value)", source)

        self.assertIn('QPushButton("Open Backend Settings")', source)
        self.assertIn("QGIS Python fallback environment", source)
        self.assertIn("Technical dependency details", source)

    def test_environment_check_algorithm_uses_shared_report_formatter(self) -> None:
        source = (ROOT / "pyforestscan_qgis/algorithms/placeholder_algorithms.py").read_text(encoding="utf-8")

        self.assertIn("report = collect_environment_report(plugin_path=plugin_root())", source)
        self.assertIn("rendered_report = format_environment_report(report)", source)
        self.assertIn("return {self.OUTPUT_MESSAGE: rendered_report}", source)


if __name__ == "__main__":
    unittest.main()
