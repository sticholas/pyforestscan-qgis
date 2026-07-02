"""Static tests for Phase 22B Mission Control Settings PBM controls."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BackendSettingsUiStaticTests(unittest.TestCase):
    """Audit Settings-page PBM controls without importing QGIS."""

    def test_install_button_remains_disabled_and_planned(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Install Backend (Planned)")', source)
        self.assertIn("self.install_backend_button.setEnabled(False)", source)
        self.assertIn("backend_install_enabled", source)
        self.assertIn('QPushButton("Install Backend Experimental")', source)
        self.assertIn("self.install_backend_button.clicked.connect(self.install_backend_experimental)", source)

    def test_phase_22b_preview_and_compatibility_buttons_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Preview Install Plan")', source)
        self.assertIn('QPushButton("Verify QGIS Compatibility")', source)
        self.assertIn("preview_install_plan", source)
        self.assertIn("verify_qgis_compatibility", source)
        self.assertIn("Installation is not enabled for normal users", source)

    def test_release_readiness_and_manual_setup_guidance_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Manual Setup Instructions")', source)
        self.assertIn("ZIP install ready", source)
        self.assertIn("Backend auto-install ready: no", source)
        self.assertIn("Manual dependency setup required", source)
        self.assertIn("QGIS Python, not system Python", source)



if __name__ == "__main__":
    unittest.main()
