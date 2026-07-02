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
        self.assertNotIn("self.install_backend_button.clicked.connect", source)

    def test_phase_22b_preview_and_compatibility_buttons_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Preview Install Plan")', source)
        self.assertIn('QPushButton("Verify QGIS Compatibility")', source)
        self.assertIn("preview_install_plan", source)
        self.assertIn("verify_qgis_compatibility", source)
        self.assertIn("Installation is not enabled yet", source)


if __name__ == "__main__":
    unittest.main()
