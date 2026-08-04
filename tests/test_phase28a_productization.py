"""QGIS-free regression checks for Phase 28A productization."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase28AProductizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mission = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        cls.pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()

    def test_primary_sidebar_is_product_focused(self):
        expected = '(\n        "Batch",\n        "Results",\n        "Scientific Advisor",\n        "Environment",\n        "Settings",\n        "Advanced Toolbox",\n    )'
        self.assertIn("PAGE_NAMES = " + expected, self.mission)

    def test_legacy_pages_remain_internal(self):
        self.assertIn("INTERNAL_PAGE_NAMES", self.mission)
        for name in ("Home", "Workspace", "Dataset", "Planning", "Processing"):
            self.assertIn(f'"{name}"', self.mission)
        self.assertIn("self.page_by_name", self.mission)

    def test_batch_is_default_workspace(self):
        self.assertIn("self.ui.pageStack.setCurrentWidget(self.batch_page)", self.mission)
        self.assertIn('self._navigate_to("Batch")', self.mission)

    def test_simplified_product_language_exists(self):
        for label in ("LiDAR Folder Selection", "Polygon Selection", "Prerun Check", "Process LiDAR"):
            self.assertIn(label, self.pages)

    def test_repository_and_spatial_tools_are_collapsed(self):
        self.assertIn('_collapsible_section(polygon_layout, "Repository Tools", checked=False)', self.pages)
        self.assertIn('_collapsible_section(polygon_layout, "Map and Spatial Tools", checked=False)', self.pages)

    def test_required_primary_repository_controls_remain(self):
        for label in ("Browse Repository", "Repository needs attention", "Build Index", "Update Index"):
            self.assertIn(label, self.pages)

    def test_results_prioritize_loading(self):
        self.assertIn('self.add_section("Generated Outputs")', self.pages)
        self.assertIn('QPushButton("Load into QGIS")', self.pages)
        self.assertIn('"Processing Summary and Diagnostics", checked=False', self.pages)

    def test_backend_and_processing_modules_are_untouched_by_phase_test_scope(self):
        self.assertIn("AdvancedToolboxPage", self.mission)
        self.assertIn("advanced_toolbox_page.open_toolbox()", self.mission)


if __name__ == "__main__":
    unittest.main()
