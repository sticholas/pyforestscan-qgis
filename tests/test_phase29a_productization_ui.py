"""QGIS-free structural contracts for Phase 29A productization UI."""
from pathlib import Path
import unittest
from pyforestscan_qgis.core.batch_control_visibility import batch_control_visibility

ROOT=Path(__file__).resolve().parents[1]
PAGES=(ROOT/'pyforestscan_qgis/ui/pages.py').read_text(encoding='utf-8')
MISSION=(ROOT/'pyforestscan_qgis/ui/mission_control.py').read_text(encoding='utf-8')

class Phase29AProductizationUiTests(unittest.TestCase):
    def test_empty_and_populated_file_list_are_adaptive(self):
        self.assertIn('self.file_list.setVisible(False)', PAGES)
        self.assertIn('COMPACT_VISIBLE_ROWS = 6', PAGES)
        self.assertIn('_size_list_to_content(self.file_list, row_height=72)', PAGES)

    def test_product_settings_follow_selection(self):
        self.assertIn('self.advanced_product_settings_group.setVisible(bool(selected))', PAGES)
        self.assertIn('ProductType.CANOPY_COVER in selected', PAGES)
        self.assertIn('ProductType.CHM in selected', PAGES)

    def test_parallel_controls_are_adaptive(self):
        automatic=batch_control_visibility(profile='recommended',execution_mode='parallel_safe',polygon_mode=False,repository_selected=False)
        custom=batch_control_visibility(profile='custom',execution_mode='parallel_safe',polygon_mode=False,repository_selected=False)
        self.assertFalse(automatic.maximum_workers)
        self.assertTrue(custom.maximum_workers)
        self.assertFalse(custom.parallel_confirmation)
        self.assertIn('addItem("Parallel", PARALLEL_SAFE_MODE)', PAGES)

    def test_readiness_report_is_always_content_sized(self):
        self.assertIn('self.preflight_text.textChanged.connect', PAGES)
        self.assertNotIn('_collapsible_section(prerun_layout, "Technical Report"', PAGES)

    def test_secondary_tools_and_backend_actions_are_progressively_disclosed(self):
        self.assertIn('"Additional Tools", checked=False', PAGES)
        self.assertIn('backend_detail_layout.addLayout(self.backend_secondary_buttons)', PAGES)
        self.assertIn('backend_detail_layout.addWidget(self.backend_technical_log_group)', PAGES)

    def test_live_status_strip_is_responsive_and_textual(self):
        self.assertIn('self.ui.statusFrame.setVisible(True)', MISSION)
        self.assertIn('compact = self.width() < 620', MISSION)
        self.assertIn('Backend:', MISSION)
        self.assertIn('Status:', MISSION)

if __name__=='__main__': unittest.main()
