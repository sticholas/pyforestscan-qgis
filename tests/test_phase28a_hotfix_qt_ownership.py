"""Regression checks for Phase 28A Batch Qt ownership."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BatchQtOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        cls.mission = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()

    def test_products_section_is_inserted_as_widget_at_creation(self):
        self.assertIn('self.products_section, products_layout = self.create_section(', self.pages)
        self.assertIn('index=self.content_layout.indexOf(self.output_section)', self.pages)
        batch = self.pages[self.pages.index("class BatchPage"):self.pages.index("class ResultsPage")]
        self.assertNotIn('products.parentWidget()', batch)
        self.assertNotIn('removeWidget(products', batch)

    def test_major_batch_sections_are_explicit_widgets(self):
        for name in (
            "mode_section", "repository_section", "polygon_section", "products_section",
            "output_section", "prerun_section", "process_section",
            "advanced_batch_section", "advanced_repository_section", "advanced_spatial_section",
        ):
            self.assertIn(f"self.{name}", self.pages)

    def test_section_factory_returns_widget_and_live_layout_contract(self):
        self.assertIn('def create_section(self, title: str, index: int | None = None) -> tuple[QGroupBox, QVBoxLayout]:', self.pages)
        self.assertIn('group = QGroupBox(title, self.content_widget)', self.pages)
        self.assertIn('layout = QVBoxLayout(group)', self.pages)
        self.assertIn('self.content_layout.insertWidget(index, group)', self.pages)

    def test_phase28a_navigation_and_default_batch_remain(self):
        for label in ("Batch", "Results", "Scientific Advisor", "Environment", "Settings", "Advanced Toolbox"):
            self.assertIn(f'"{label}"', self.mission)
        self.assertIn('self.ui.pageStack.setCurrentWidget(self.batch_page)', self.mission)

    def test_hidden_pages_remain_internal(self):
        self.assertIn("INTERNAL_PAGE_NAMES", self.mission)
        for label in ("Home", "Workspace", "Dataset", "Planning", "Processing"):
            self.assertIn(f'"{label}"', self.mission)

    def test_no_batch_layout_reordering_through_parent_widget(self):
        batch = self.pages[self.pages.index("class BatchPage"):self.pages.index("class ResultsPage")]
        self.assertNotIn(".parentWidget()", batch)
        self.assertNotIn("removeWidget(", batch)

    def test_plugin_unload_uses_single_qt_owned_cleanup_path(self):
        plugin = (ROOT / "pyforestscan_qgis/plugin.py").read_text()
        unload = plugin[plugin.index("    def unload"):plugin.index("    def _create_mission_control_action")]
        self.assertEqual(unload.count("self.mission_control.deleteLater()"), 1)
        self.assertIn("self.mission_control = None", unload)
        self.assertIn("self.provider = None", unload)
        self.assertNotIn("sip.delete", unload)
        self.assertNotIn("setLayout(", unload)


if __name__ == "__main__":
    unittest.main()
