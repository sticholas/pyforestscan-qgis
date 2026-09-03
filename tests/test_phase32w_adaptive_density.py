"""Phase 32W disclosure affordance and adaptive-density contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
STYLES = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")


class Phase32WAdaptiveDensityTests(unittest.TestCase):
    def test_shared_disclosure_has_accessible_fixed_header_and_zero_body(self) -> None:
        helper = PAGES[PAGES.index("class CompactCollapsibleSection"):PAGES.index("def _set_layout_visible")]
        self.assertIn('setAccessibleName(f"{title}, expandable section")', helper)
        self.assertIn("setFixedHeight(28)", helper)
        self.assertIn("Qt.RightArrow", helper)
        self.assertIn("Qt.DownArrow", helper)
        self.assertIn("content.setMaximumHeight(0)", helper)
        self.assertIn("layout.sizeHint().height()", helper)

    def test_disclosure_has_subtle_hover_and_focus_treatment(self) -> None:
        self.assertIn("QToolButton#compactCollapsibleHeader:hover", STYLES)
        self.assertIn("QToolButton#compactCollapsibleHeader:focus", STYLES)

    def test_advanced_and_details_use_shared_disclosure(self) -> None:
        self.assertIn('_collapsible_section(products_layout, "Advanced Scientific Settings", checked=False)', PAGES)
        self.assertIn('_collapsible_section(prerun_layout, "Details", checked=False)', PAGES)
        self.assertIn('_collapsible_section(self.content_layout, "Details", checked=False)', PAGES)

    def test_processing_visibility_is_state_driven(self) -> None:
        density = PAGES[PAGES.index("def _update_processing_density"):PAGES.index("def _reconcile_processing_ui")]
        for widget in ("progress_bar", "engine_status_label", "worker_status_label", "summary_label"):
            self.assertIn(f"self.{widget}.setVisible(active)", density)
        self.assertIn("ProcessingUiState.COMPLETE", density)
        self.assertIn("_refresh_layout_geometry(self.process_section)", density)

    def test_tools_setup_is_compact_and_state_aware(self) -> None:
        settings = PAGES[PAGES.index("class SettingsPage"):PAGES.index("def register_context_help")]
        self.assertIn('_collapsible_section(self.content_layout, "Preferences", checked=False)', settings)
        self.assertIn('QPushButton("Recheck")', settings)
        self.assertIn("self.content_layout.addStretch(1)", settings)
        self.assertIn("self.install_backend_button.setVisible(action_visible)", settings)
        self.assertIn('self.open_diagnostics_button.setVisible(repair or status in {"FAILED", "INCOMPATIBLE"})', settings)

    def test_collapsible_help_is_explicit(self) -> None:
        self.assertIn("Adjust optional scientific parameters for the products you selected.", PAGES)
        self.assertIn("Show additional technical information about the current operation.", PAGES)


if __name__ == "__main__":
    unittest.main()
