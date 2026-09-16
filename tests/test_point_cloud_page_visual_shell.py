"""QGIS-free UI contract for the native Point Cloud controls around the renderer."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PointCloudPageVisualShellTests(unittest.TestCase):
    def test_compact_material_inspired_native_shell_is_scoped_to_point_cloud_page(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text(encoding="utf-8")
        self.assertIn('self.setObjectName("pointCloudPage")', source)
        self.assertIn('QWidget#pointCloudPage QPushButton[pointCloudRole="primary"]', source)
        self.assertIn('QWidget#pointCloudPage QToolButton[pointCloudControl="true"]', source)
        self.assertIn('QWidget#pointCloudPage QTabBar::tab:selected', source)

    def test_primary_actions_and_compact_navigation_are_accessible(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text(encoding="utf-8")
        self.assertIn('self.open_button.setProperty("pointCloudRole", "primary")', source)
        self.assertIn('self.open_button.setAccessibleName("Open point cloud")', source)
        self.assertIn('self.navigation_hint.setProperty("pointCloudHint", True)', source)
        self.assertIn("wheel zoom to cursor", source)
        self.assertIn('self.overlay_button.setAccessibleName("Scientific overlays")', source)
