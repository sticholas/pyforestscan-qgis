"""Actual Qt event tests; headless tiers skip when QGIS Qt is unavailable."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, Qt
    from qgis.PyQt.QtGui import QMouseEvent
    from qgis.PyQt.QtWidgets import QApplication
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.ui.point_cloud_detached import LinkedTabBar
    from pyforestscan_qgis.ui.point_cloud_tools import SelectionTools
    from pyforestscan_qgis.ui.point_cloud_linked_views import LinkedViews
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class TabDetachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tabs = LinkedTabBar()
        self.tabs.resize(400, 32)
        self.tabs.setMovable(True)
        for title in ("Overview", "Area Detail", "Slice"):
            index = self.tabs.addTab(title)
            self.tabs.setTabData(index, title)
        self.events = []
        self.tabs.detachRequested.connect(lambda *args: self.events.append(args))

    def tearDown(self):
        self.tabs.close()
        self.tabs.deleteLater()
        self.app.processEvents()

    def event(self, kind, point, pressed):
        left = qt_enum(Qt, "LeftButton", "MouseButton")
        none = qt_enum(Qt, "NoButton", "MouseButton")
        button = none if kind == "MouseMove" else left
        value = QMouseEvent(qt_enum(QEvent, kind, "Type"), QPointF(point),
            QPointF(self.tabs.mapToGlobal(point)), button, left if pressed else none,
            qt_enum(Qt, "NoModifier", "KeyboardModifier"))
        QApplication.sendEvent(self.tabs, value)
        self.app.processEvents()

    def test_crossing_boundary_detaches_once_before_external_release(self):
        start = self.tabs.tabRect(1).center()
        self.event("MouseButtonPress", start, True)
        self.event("MouseMove", QPoint(start.x(), 80), True)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][0], "Area Detail")
        self.event("MouseButtonRelease", QPoint(start.x(), 80), False)
        self.assertEqual(len(self.events), 1)

    def test_click_does_not_detach(self):
        start = self.tabs.tabRect(1).center()
        self.event("MouseButtonPress", start, True)
        self.event("MouseButtonRelease", start, False)
        self.assertFalse(self.events)

    def test_tab_reordering_does_not_detach(self):
        start = self.tabs.tabRect(1).center()
        target = self.tabs.tabRect(2).center()
        self.event("MouseButtonPress", start, True)
        self.event("MouseMove", target, True)
        self.event("MouseButtonRelease", target, False)
        self.assertFalse(self.events)

    def test_external_release_fallback(self):
        start = self.tabs.tabRect(2).center()
        self.event("MouseButtonPress", start, True)
        self.event("MouseButtonRelease", QPoint(start.x(), 100), False)
        self.assertEqual(self.events[0][0], "Slice")


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class SelectionToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tools = SelectionTools()
        self.events = []
        self.tools.currentTextChanged.connect(self.events.append)

    def tearDown(self):
        self.tools.deleteLater()
        self.app.processEvents()

    def test_direct_icons_are_named_and_have_semantic_help(self):
        for button in self.tools.buttons.values():
            self.assertFalse(button.icon().isNull())
            self.assertTrue(button.accessibleName())
            self.assertGreater(len(button.toolTip()), 40)
            self.assertEqual(button.width(), 28)
            self.assertEqual(button.height(), 28)

    def test_exclusive_buttons_dispatch_existing_tool_names(self):
        self.tools.buttons["Polygon"].click()
        self.assertEqual(self.events, ["Polygon"])
        self.assertEqual(self.tools.currentText(), "Polygon")
        self.assertFalse(self.tools.buttons["Pointer"].isChecked())
        self.assertTrue(self.tools.buttons["Polygon"].isChecked())

    def test_reset_and_rearm_without_a_hidden_combo(self):
        self.tools.setCurrentText("Rectangle")
        self.tools.blockSignals(True)
        self.tools.setCurrentText("Pointer")
        self.tools.blockSignals(False)
        self.assertEqual(self.events, ["Rectangle"])
        self.tools.buttons["Pointer"].click()
        self.assertEqual(self.events, ["Rectangle", "Pointer"])

    def test_busy_disables_every_tool_and_unknown_values_are_ignored(self):
        self.tools.setCurrentText("not-a-tool")
        self.assertEqual(self.tools.currentText(), "Pointer")
        self.tools.setEnabled(False)
        self.assertTrue(all(not button.isEnabled() for button in self.tools.buttons.values()))

    def test_selection_detail_margin_is_zero_by_default_and_only_expands_region(self):
        owner = SimpleNamespace(page=SimpleNamespace(editor=SimpleNamespace(state={
            "selection": {"bounds": [0, 0, 5, 10, 20, 15]}, "source_crs": "EPSG:6635"})),
            add=Mock())
        with patch("pyforestscan_qgis.ui.point_cloud_linked_views.QInputDialog.getDouble",
                   return_value=(0, True)) as dialog:
            LinkedViews.from_selection(owner)
        self.assertEqual(dialog.call_args.args[3], 0)
        self.assertIn("Extra margin on each side", dialog.call_args.args[2])
        region = owner.add.call_args.args[1]
        self.assertEqual(region["width"], 10)
        self.assertEqual(region["height"], 20)
        with patch("pyforestscan_qgis.ui.point_cloud_linked_views.QInputDialog.getDouble",
                   return_value=(2, True)):
            LinkedViews.from_selection(owner)
        self.assertEqual(owner.add.call_args.args[1]["width"], 14)
        self.assertEqual(owner.add.call_args.args[1]["height"], 24)


if __name__ == "__main__":
    unittest.main()
