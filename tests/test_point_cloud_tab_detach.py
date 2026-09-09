"""Actual Qt event tests; headless tiers skip when QGIS Qt is unavailable."""
import unittest

try:
    from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, Qt
    from qgis.PyQt.QtGui import QMouseEvent
    from qgis.PyQt.QtWidgets import QApplication
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.ui.point_cloud_detached import LinkedTabBar
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


if __name__ == "__main__":
    unittest.main()
