"""Phase 32V compact density and selected-map-feature contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class Phase32VCompactDensityTests(unittest.TestCase):
    def test_process_configuration_is_content_sized(self) -> None:
        batch_start = PAGES.index('super().__init__("Process", parent)')
        self.assertIn("self.content_layout.setSizeConstraint(QLayout.SetNoConstraint)", PAGES[batch_start:batch_start + 300])
        install = PAGES[PAGES.index("def _install_process_workspace"):PAGES.index("def _apply_process_layout")]
        self.assertIn("QSizePolicy.Expanding, QSizePolicy.Maximum", install)
        self.assertIn("self.process_workspace_layout.addStretch(1)", install)
        self.assertIn("setSizeConstraint(QLayout.SetNoConstraint)", install)

    def test_collapsible_body_has_true_zero_height(self) -> None:
        helper = PAGES[PAGES.index("def _collapsible_section"):PAGES.index("def _set_layout_visible")]
        self.assertIn('setProperty("compactCollapsible", True)', helper)
        self.assertIn("content.setMaximumHeight(16777215 if visible else 0)", helper)
        self.assertIn("content.setVisible(visible)", helper)

    def test_compact_spacing_and_help_bounds(self) -> None:
        self.assertIn("SECTION_MARGINS = (SPACING_XS, SPACING_XS, SPACING_XS, SPACING_XS)", PAGES)
        self.assertIn("SECTION_GAP = SPACING_SM", PAGES)
        self.assertIn("self.setMaximumHeight(42)", PAGES)

    def test_actions_share_equal_geometry_contract(self) -> None:
        install = PAGES[PAGES.index("def _install_process_workspace"):PAGES.index("def _apply_process_layout")]
        responsive = PAGES[PAGES.index("def _apply_process_layout"):PAGES.index("def resizeEvent")]
        self.assertIn("equal_height = max", install)
        self.assertIn("self.preflight_button.setFixedHeight(equal_height)", install)
        self.assertIn("self.run_button.setFixedHeight(equal_height)", install)
        self.assertNotIn("self.run_button.setMaximumWidth", PAGES)
        self.assertIn("setColumnStretch(0, 1)", responsive)
        self.assertIn("setColumnStretch(1, 1 if width >= 420 else 0)", responsive)

    def test_compact_headings_do_not_depend_on_groupbox_title_margins(self) -> None:
        install = PAGES[PAGES.index("def _install_process_workspace"):PAGES.index("def _apply_process_layout")]
        self.assertIn("compact_headings = (", install)
        self.assertIn('heading.setObjectName("compactSectionHeading")', install)
        self.assertIn('self.output_row.insertWidget(0, output_heading, 0)', install)

    def test_area_actions_wrap_at_narrow_width(self) -> None:
        responsive = PAGES[PAGES.index("def _apply_process_layout"):PAGES.index("def resizeEvent")]
        self.assertIn("if width < 480:", responsive)
        self.assertIn("self.use_selected_features_button, 1, 0, 1, 2", responsive)
        self.assertIn("self.polygon_layer_mode_combo, 1, 0", responsive)

    def test_selected_features_action_reuses_normalization_contract(self) -> None:
        self.assertIn('QPushButton("Use Selected Features")', PAGES)
        action = PAGES[PAGES.index("def use_selected_polygon_features"):PAGES.index("def _update_polygon_source_visibility")]
        self.assertIn('findData("selected")', action)
        self.assertIn("self._publish_session_state()", action)
        self.assertNotIn("run_preflight", action)
        normalization = PAGES[PAGES.index("def _normalized_polygon_selection"):PAGES.index("def reset_polygon_batch")]
        self.assertIn("normalize_qgis_layer_selection", normalization)
        self.assertIn('use_selected=self.polygon_layer_mode_combo.currentData() == "selected"', normalization)

    def test_product_visibility_reflows_only_when_expanded(self) -> None:
        refresh = PAGES[PAGES.index("def _refresh_batch_option_visibility"):PAGES.index("def _update_adaptive_visibility")]
        self.assertIn("if self.advanced_product_settings_group.isChecked()", refresh)
        self.assertIn("_refresh_layout_geometry(self.advanced_product_settings_group)", refresh)

    def test_scientific_advanced_excludes_repository_maintenance(self) -> None:
        start = PAGES.index('"Advanced Scientific Settings"')
        end = PAGES.index("self.refresh_processing_status_button", start)
        scientific = PAGES[start:end]
        self.assertNotIn("settings_layout.addWidget(self.retain_unmasked_intermediate_check)", scientific)
        self.assertNotIn("settings_layout.addLayout(repository_maintenance)", scientific)


if __name__ == "__main__":
    unittest.main()
