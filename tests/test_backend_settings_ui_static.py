"""Static tests for Phase 22B Mission Control Settings PBM controls."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BackendSettingsUiStaticTests(unittest.TestCase):
    """Audit Settings-page PBM controls without importing QGIS."""

    def test_install_button_uses_internal_beta_availability(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("install_availability.button_label", source)
        self.assertIn("self.install_backend_button.setEnabled(install_availability.enabled)", source)
        self.assertIn("self.install_backend_button.clicked.connect(self.install_backend_internal_beta)", source)
        self.assertIn("This will install PyForestScan backend packages into your user-local PyForestScan folder", source)
        self.assertIn("It will not modify QGIS or system Python", source)

    def test_phase_22b_preview_and_compatibility_buttons_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Preview Install Plan")', source)
        self.assertIn('QPushButton("Verify QGIS Compatibility")', source)
        self.assertIn("preview_install_plan", source)
        self.assertIn("verify_qgis_compatibility", source)
        self.assertIn("Windows internal beta builds can install a user-local backend", source)

    def test_release_readiness_and_manual_setup_guidance_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Manual Setup Instructions")', source)
        self.assertIn("ZIP install ready", source)
        self.assertIn("Backend auto-install ready", source)
        self.assertIn("Manual dependency setup required", source)
        self.assertIn("Backend auto-install ready: yes for Windows internal beta builds after confirmation", source)


    def test_backend_install_progress_ui_and_worker_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("class _BackendInstallWorker(QObject)", source)
        self.assertIn("progressUpdated = pyqtSignal(object)", source)
        self.assertIn("self.backend_install_progress_bar", source)
        self.assertIn("Install stage:", source)
        self.assertIn("Current package/action:", source)
        self.assertIn("Elapsed time:", source)
        self.assertIn("Latest message:", source)
        self.assertIn("Step progress is estimated.", source)
        self.assertIn("Advanced / Troubleshooting: technical log", source)

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

        self.assertIn('self.status_label.setText(f"Status: {report.readiness.value}")', source)
        self.assertIn("self.environmentChanged.emit(report.readiness.value)", source)

    def test_environment_check_algorithm_uses_shared_report_formatter(self) -> None:
        source = (ROOT / "pyforestscan_qgis/algorithms/placeholder_algorithms.py").read_text(encoding="utf-8")

        self.assertIn("report = collect_environment_report(plugin_path=plugin_root())", source)
        self.assertIn("rendered_report = format_environment_report(report)", source)
        self.assertIn("return {self.OUTPUT_MESSAGE: rendered_report}", source)


if __name__ == "__main__":
    unittest.main()
