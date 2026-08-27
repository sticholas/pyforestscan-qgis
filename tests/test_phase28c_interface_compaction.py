"""Structural regression tests for Phase 28C retained-interface compaction."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
MISSION = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text(encoding="utf-8")

class Phase28CInterfaceCompactionTests(unittest.TestCase):
    def test_two_workspace_sidebar_and_process_default_are_preserved(self):
        self.assertIn('PAGE_NAMES = ("Process", "Tools & Setup")', MISSION)
        self.assertIn("self.ui.pageStack.setCurrentWidget(self.batch_page)", MISSION)

    def test_hidden_pages_remain_absent_from_primary_sidebar(self):
        primary = MISSION.split("\n    PAGE_NAMES = (", 1)[1].split(")", 1)[0]
        for name in ("Home", "Workspace", "Dataset", "Planning", "Processing"):
            self.assertNotIn(f'"{name}"', primary)

    def test_mode_switch_hides_irrelevant_sections(self):
        self.assertIn("self.standard_batch_section.setVisible(not polygon)", PAGES)
        self.assertIn("self.polygon_batch_section.setVisible(polygon)", PAGES)
        self.assertIn("Process LiDAR covering a selected polygon.", PAGES)
        self.assertIn("Process LiDAR files found in a selected folder.", PAGES)

    def test_normal_batch_flow_uses_compact_section_names(self):
        for title in ("Processing Mode", "LiDAR Data", "Processing Area", "Products", "Output Folder", "Readiness", "Process", "Current Result"):
            self.assertIn(f'create_section("{title}"', PAGES)
        self.assertNotIn('_collapsible_section(self.content_layout, "Batch Footprint Estimate"', PAGES)

    def test_specialist_controls_are_collapsed(self):
        for title in ("Repository Tools", "Map and Spatial Tools", "Advanced Product Settings", "Advanced Batch Options"):
            self.assertIn(f'"{title}", checked=False', PAGES)
        self.assertNotIn('"Additional Tools", checked=False', PAGES)

    def test_key_summary_widgets_are_content_bounded(self):
        self.assertIn("_size_text_edit_to_content(self.preflight_text)", PAGES)
        self.assertIn("self.previous_reports.setMaximumHeight(120)", PAGES)
        self.assertIn("self.fallback_checks_list.setMaximumHeight(140)", PAGES)
        self.assertIn("self.checks_list.setMaximumHeight(180)", PAGES)
        self.assertIn("self.backend_details.setMaximumHeight(140)", PAGES)

    def test_results_empty_and_populated_states_are_distinct(self):
        self.assertIn("No products have been generated yet.", PAGES)
        self.assertIn('QPushButton("Go to Batch")', PAGES)
        self.assertIn("def _sync_compact_visibility", PAGES)
        self.assertIn("self.go_to_batch_button.setVisible(not has_outputs)", PAGES)
        self.assertIn("self.load_outputs_button.setVisible(has_outputs)", PAGES)

    def test_advisor_hides_empty_sections_and_normal_signature(self):
        self.assertIn("self.recommendations_card.setVisible(bool(summary.key_recommendations))", PAGES)
        self.assertIn("self.warnings_card.setVisible(bool(summary.warnings))", PAGES)
        self.assertIn("Guidance reflects the current Batch selections.", PAGES)
        self.assertNotIn('self.session_context_label.setText(f"Current state:', PAGES)

    def test_environment_and_settings_use_progressive_disclosure(self):
        self.assertIn('"QGIS Python fallback environment", checked=False', PAGES)
        self.assertIn('"Technical dependency details", checked=False', PAGES)
        self.assertIn('self.add_section("Advanced Settings")', PAGES)
        self.assertNotIn('"Advanced Settings", checked=False', PAGES)
        self.assertIn('"Troubleshooting", checked=False', PAGES)

    def test_primary_action_and_toolbox_contract(self):
        self.assertIn("self.resume_button.setVisible(enabled and resumable)", PAGES)
        self.assertIn('QPushButton("Open Processing Toolbox")', PAGES)
        self.assertIn('QPushButton("Refresh Tools")', PAGES)
        self.assertIn('QPushButton("View Tool Documentation")', PAGES)

    def test_accessibility_and_native_icons_remain(self):
        self.assertIn('self.batch_mode_combo.setAccessibleName("Processing mode")', PAGES)
        self.assertIn("QgsApplication.getThemeIcon", PAGES)
        self.assertIn("getattr(QStyle, pixmap_name", PAGES)
        self.assertIn("setWordWrap(True)", PAGES)

if __name__ == "__main__":
    unittest.main()
