"""QGIS-free regressions for visible viewer activity and direct mouse navigation."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ViewerLoadingAndNavigationTests(unittest.TestCase):
    def test_renderer_has_compact_busy_indicator_and_selection_bridge(self):
        html = (ROOT / "pyforestscan_qgis" / "viewer" / "viewer.html").read_text(encoding="utf-8")
        javascript = (ROOT / "pyforestscan_qgis" / "viewer" / "viewer.js").read_text(encoding="utf-8")
        editor = (ROOT / "pyforestscan_qgis" / "ui" / "point_cloud_editor.py").read_text(encoding="utf-8")
        self.assertIn('id="viewer-busy"', html)
        self.assertIn("function setViewerBusy", javascript)
        self.assertIn('action === "viewer_busy"', javascript)
        self.assertIn('"Resolving selected source points"', editor)

    def test_navigation_uses_cursor_wheel_and_middle_pan_without_mode_dropdown(self):
        page = (ROOT / "pyforestscan_qgis" / "ui" / "point_cloud_page.py").read_text(encoding="utf-8")
        javascript = (ROOT / "pyforestscan_qgis" / "viewer" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn("wheel zoom to cursor", page)
        self.assertNotIn("self.navigation_mode = QComboBox()", page)
        self.assertIn("Potree.MOUSE.MIDDLE", javascript)
        self.assertIn("getMousePointCloudIntersection", javascript)
        self.assertIn('state.navigation = "CURSOR_ORBIT"', javascript)
        ui_sources = "\n".join(item.read_text(encoding="utf-8") for item in
                               (ROOT / "pyforestscan_qgis" / "ui").glob("*.py"))
        self.assertNotIn(".navigation_mode", ui_sources)
        self.assertIn("navigation_hint", ui_sources)

    def test_qt_status_supports_non_blocking_busy_animation(self):
        widgets = (ROOT / "pyforestscan_qgis" / "ui" / "point_cloud_widgets.py").read_text(encoding="utf-8")
        self.assertIn("def setBusy", widgets)
        self.assertIn("QTimer", widgets)
        self.assertIn("Working ", widgets)


if __name__ == "__main__":
    unittest.main()
