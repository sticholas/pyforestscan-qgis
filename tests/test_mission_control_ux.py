"""QGIS-free tests for Mission Control beta UX summary language."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.ui.ux_summary import (
    backend_summary_from_environment,
    button_role_for_label,
    design_spacing_tokens,
    design_status_labels,
    empty_state_message,
    environment_headline,
    expandable_section_labels,
    primary_action_label,
    qgis_fallback_summary,
    status_badge_tone,
    routed_products_summary,
    technical_sections_default_collapsed,
    workflow_action_labels,
)

ROOT = Path(__file__).resolve().parents[1]


class MissionControlUxTests(unittest.TestCase):
    """Verify compact workflow labels without importing QGIS."""

    def test_home_action_labels_match_beta_workflow(self) -> None:
        self.assertEqual(workflow_action_labels(), ("Open Dataset", "Start Batch", "Continue Previous Session"))

    def test_empty_states_are_concise_guidance(self) -> None:
        self.assertEqual(empty_state_message("advisor"), "Analyze a dataset to receive recommendations.")
        self.assertEqual(empty_state_message("results"), "Run processing to generate output products.")
        self.assertEqual(empty_state_message("workspace"), "Open or create a workspace to begin.")

    def test_primary_action_labels_are_standardized(self) -> None:
        self.assertEqual(primary_action_label("dataset"), "Analyze Dataset")
        self.assertEqual(primary_action_label("processing"), "Run Processing")
        self.assertEqual(primary_action_label("settings"), "Verify Backend")

    def test_design_system_status_badges_are_standardized(self) -> None:
        self.assertEqual(design_status_labels(), ("READY", "RUNNING", "WARNING", "FAILED", "NOT CONFIGURED", "DISABLED", "PLANNED"))
        self.assertEqual(status_badge_tone("READY"), "success")
        self.assertEqual(status_badge_tone("not_configured"), "neutral")
        self.assertEqual(status_badge_tone("FAILED"), "danger")

    def test_design_system_button_roles_are_standardized(self) -> None:
        self.assertEqual(button_role_for_label("Run Processing"), "primary")
        self.assertEqual(button_role_for_label("Open Output Folder"), "secondary")
        self.assertEqual(button_role_for_label("Refresh Environment"), "neutral")
        self.assertEqual(button_role_for_label("Clear Current Run"), "danger")

    def test_design_system_spacing_and_expandable_labels(self) -> None:
        self.assertEqual(design_spacing_tokens(), {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24})
        self.assertEqual(expandable_section_labels(), ("Advanced", "Technical Details", "Troubleshooting"))

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
        self.assertIn('Advanced / Troubleshooting: backend details', source)
        self.assertIn('self.recommendations_card.setVisible(bool(report.suggested_next_actions))', source)
        self.assertIn('self.warnings_card.setVisible(bool(report.warnings))', source)
        self.assertIn('self.jobs_section.setVisible(False)', source)

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
