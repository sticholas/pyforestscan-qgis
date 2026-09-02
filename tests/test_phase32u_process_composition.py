"""Phase 32U Process-page information architecture contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
STYLES = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")


class Phase32UProcessCompositionTests(unittest.TestCase):
    def test_major_workflow_is_one_vertical_stack(self) -> None:
        install = PAGES[PAGES.index("def _install_process_workspace"):PAGES.index("def _apply_process_layout")]
        self.assertIn("QVBoxLayout(self.process_workspace)", install)
        self.assertNotIn("QGridLayout(self.process_workspace)", install)
        expected = (
            "self.mode_section, self.repository_section, self.polygon_section,\n"
            "            self.products_section, self.output_section, self.prerun_section, self.process_section"
        )
        self.assertIn(expected, install)

    def test_responsiveness_is_internal_to_products_and_advanced(self) -> None:
        responsive = PAGES[PAGES.index("def _apply_process_layout"):PAGES.index("def resizeEvent")]
        self.assertIn("columns = 4 if width >= 720 else 2", responsive)
        self.assertIn("self.product_grid.addWidget", responsive)
        self.assertIn("self.product_settings_form.setRowWrapPolicy", responsive)
        self.assertNotIn("self.process_workspace_layout.addWidget", responsive)

    def test_products_advanced_output_order_is_explicit(self) -> None:
        self.assertLess(PAGES.index('create_section("Products"'), PAGES.index('"Advanced Scientific Settings"'))
        self.assertLess(PAGES.index('"Advanced Scientific Settings"'), PAGES.index("def _install_process_workspace"))
        install = PAGES[PAGES.index("def _install_process_workspace"):PAGES.index("def _apply_process_layout")]
        self.assertLess(install.index("self.products_section"), install.index("self.output_section"))

    def test_prerun_and_process_share_primary_action_row(self) -> None:
        responsive = PAGES[PAGES.index("def _apply_process_layout"):PAGES.index("def resizeEvent")]
        self.assertIn("self.workflow_action_row.addWidget(self.preflight_button", responsive)
        self.assertIn("self.workflow_action_row.addWidget(self.run_button", responsive)

    def test_area_utilities_do_not_stretch(self) -> None:
        self.assertIn("polygon_area_actions.addWidget(self.polygon_refresh_layers_button, 0)", PAGES)
        self.assertIn("polygon_area_actions.addWidget(self.zoom_polygon_button, 0)", PAGES)

    def test_process_sections_are_frameless_and_help_is_bounded(self) -> None:
        self.assertIn('QGroupBox[processSection="true"]', STYLES)
        self.assertIn("self.setMaximumHeight(54)", PAGES)

    def test_design_metrics_are_centralized(self) -> None:
        for token in ("PAGE_MARGIN", "SECTION_GAP", "ROW_GAP", "CONTROL_GAP", "HEADING_GAP", "COMPACT_BUTTON_HEIGHT", "FIELD_HEIGHT"):
            self.assertIn(f"{token} =", PAGES)


if __name__ == "__main__":
    unittest.main()
