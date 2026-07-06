"""QGIS-free tests for Mission Control beta UX summary language."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.ui.ux_summary import (
    backend_summary_from_environment,
    environment_headline,
    qgis_fallback_summary,
    routed_products_summary,
    technical_sections_default_collapsed,
    workflow_action_labels,
)

ROOT = Path(__file__).resolve().parents[1]


class MissionControlUxTests(unittest.TestCase):
    """Verify compact workflow labels without importing QGIS."""

    def test_home_action_labels_match_beta_workflow(self) -> None:
        self.assertEqual(workflow_action_labels(), ("Start Single Dataset", "Start Batch", "Continue Last Run"))

    def test_backend_ready_summary_is_not_scary(self) -> None:
        self.assertEqual(backend_summary_from_environment("READY"), "Backend status: PBM ready for routed products")
        self.assertIn("routed products can run through PBM", environment_headline("READY"))

    def test_product_coverage_summaries_are_explicit(self) -> None:
        self.assertIn("Dataset Explorer", routed_products_summary())
        self.assertIn("Voxel Statistic", routed_products_summary())
        self.assertIn("Height Above Ground", qgis_fallback_summary())
        self.assertTrue(technical_sections_default_collapsed())

    def test_mission_control_pages_default_technical_sections_collapsed(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("Open Backend Settings")', source)
        self.assertIn('QGIS Python fallback environment', source)
        self.assertIn('Technical dependency details', source)
        self.assertIn('Advanced Batch Options', source)
        self.assertIn('Batch Footprint Estimate', source)

    def test_workflow_buttons_and_results_buttons_are_present(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn("continueLastRequested = pyqtSignal()", source)
        self.assertIn("def set_continue_available", source)
        self.assertIn('QPushButton("Open Output Folder")', source)
        self.assertIn('QPushButton("Load Outputs")', source)
        self.assertIn('QPushButton("Clear Current Run")', source)
        self.assertIn("Execution backend: PBM when READY", source)


if __name__ == "__main__":
    unittest.main()
