"""Actual Qt event tests; headless tiers skip when QGIS Qt is unavailable."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, Qt, QObject, pyqtSignal
    from qgis.PyQt.QtGui import QMouseEvent
    from qgis.PyQt.QtWidgets import QApplication, QListWidget
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.ui.point_cloud_detached import LinkedTabBar, DetachedView
    from pyforestscan_qgis.ui.point_cloud_tools import SelectionTools
    from pyforestscan_qgis.ui.point_cloud_linked_views import LinkedViews
    from pyforestscan_qgis.ui.point_cloud_selection_limits import SelectionLimits
    from pyforestscan_qgis.ui.point_cloud_appearance import PointAppearance
    from pyforestscan_qgis.ui.point_cloud_class_visibility import ClassVisibilityMenu
    from pyforestscan_qgis.ui.point_cloud_editor import EditorPanel
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class TabDetachTests(unittest.TestCase):
    def test_detached_controls_require_authoritative_editor(self):
        editor = SimpleNamespace(worker=None, busy=False, state={"ready": True,
            "can_undo": True, "can_redo": True, "selection": {"resolved_point_count": 8}})
        window = SimpleNamespace(controller=SimpleNamespace(page=SimpleNamespace(editor=editor), depth_error=""),
            tool=Mock(), selection_mode=Mock(), classify_button=Mock(),
            action_buttons={"undo": Mock(), "redo": Mock(), "invert": Mock()}, resize_button=Mock())
        DetachedView.refresh_edit_controls(window)
        for button in (window.tool, window.selection_mode, window.classify_button,
                       *window.action_buttons.values()):
            button.setEnabled.assert_called_with(False)

    def test_detached_controls_follow_busy_selection_and_journal(self):
        editor = SimpleNamespace(worker=object(), busy=False, state={"ready": True,
            "can_undo": True, "can_redo": False, "selection": {"resolved_point_count": 8}})
        window = SimpleNamespace(controller=SimpleNamespace(page=SimpleNamespace(editor=editor), depth_error=""),
            tool=Mock(), selection_mode=Mock(), classify_button=Mock(),
            action_buttons={"undo": Mock(), "redo": Mock(), "invert": Mock()}, resize_button=Mock())
        DetachedView.refresh_edit_controls(window)
        window.classify_button.setEnabled.assert_called_with(True)
        window.action_buttons["undo"].setEnabled.assert_called_with(True)
        window.action_buttons["redo"].setEnabled.assert_called_with(False)
        window.action_buttons["invert"].setEnabled.assert_called_with(True)
        window.resize_button.setEnabled.assert_called_with(True)
        editor.busy = True
        DetachedView.refresh_edit_controls(window)
        window.tool.setEnabled.assert_called_with(False)
        window.classify_button.setEnabled.assert_called_with(False)

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

    def test_profile_line_tools_are_contextual_direct_actions(self):
        for name in ("AboveLine", "BelowLine"):
            self.assertTrue(self.tools.buttons[name].isHidden())
        self.tools.setProfileToolsVisible(True)
        for name in ("AboveLine", "BelowLine"):
            self.assertFalse(self.tools.buttons[name].isHidden())
            self.assertIn("original points", self.tools.buttons[name].toolTip())

    def test_editor_uses_complete_swatch_backed_classification_catalog(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        self.assertEqual(editor.classes.count(), 23)
        self.assertEqual(editor.classes.currentData(), 5)
        self.assertEqual(editor.classes.currentText(), "High vegetation (5)")
        self.assertTrue(all(not editor.classes.itemIcon(index).isNull()
                            for index in range(editor.classes.count())))
        self.assertEqual(editor.classes.itemData(17), 17)
        self.assertEqual(editor.classes.itemText(18), "High noise (18)")

    def test_classify_while_selecting_stages_once_only_after_select_snapshot(self):
        value = {"ready":True, "source":"source.laz", "edits":0, "point_count":100,
            "selection":{"selection_id":"selected", "resolved_point_count":12,
                         "classification_counts":[[2,12]]},
            "selection_definitions":[{"selection_mode":"REPLACE"}],
            "history":[], "overlay":"overlay.json", "revision":1}
        page = SimpleNamespace(send=Mock(), workspace=SimpleNamespace(
            accept_editor_snapshot=Mock()), linked=SimpleNamespace(sync_tabs=Mock()),
            session_status=Mock(), source=Mock(), start_source=Mock(), mode=Mock())
        owner = SimpleNamespace(pending_action="select", classify_while=SimpleNamespace(
            isChecked=lambda: True), state={}, page=page, summary=Mock(), history=Mock(),
            busy=True, cancel_requested=False, source="", restored_view=None,
            refresh_controls=Mock(), stage=Mock(), sent_overlay=None,
            exportReady=Mock(), source_changed=Mock(), code=SimpleNamespace(value=lambda:5))
        EditorPanel.update_state(owner, value)
        owner.stage.assert_called_once_with("Classification", 5)
        self.assertIsNone(owner.pending_action)
        owner.stage.reset_mock()
        EditorPanel.update_state(owner, value)
        owner.stage.assert_not_called()
        owner.pending_action = "invert"
        EditorPanel.update_state(owner, value)
        owner.stage.assert_not_called()

    def test_exclusive_buttons_dispatch_existing_tool_names(self):
        self.tools.buttons["Polygon"].click()
        self.assertEqual(self.events, ["Polygon"])
        self.assertEqual(self.tools.currentText(), "Polygon")
        self.assertFalse(self.tools.buttons["Pointer"].isChecked())
        self.assertTrue(self.tools.buttons["Polygon"].isChecked())
        self.tools.buttons["Circle"].click()
        self.assertEqual(self.events[-1], "Circle")
        self.assertTrue(self.tools.buttons["Circle"].isChecked())
        self.tools.buttons["Box"].click()
        self.assertEqual(self.events[-1], "Box")
        self.assertTrue(self.tools.buttons["Box"].isChecked())

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

    def test_brush_radius_is_contextual_and_emits_source_unit_value(self):
        radii = []
        self.tools.brushRadiusChanged.connect(radii.append)
        self.assertTrue(self.tools.brush_radius.isHidden())
        self.tools.buttons["Brush"].click()
        self.assertFalse(self.tools.brush_radius.isHidden())
        self.tools.brush_radius.setValue(2.5)
        self.assertEqual(radii, [2.5])
        self.assertEqual(self.tools.brushRadius(), 2.5)
        self.assertIn("dataset XY", self.tools.brush_radius.accessibleName())
        self.tools.buttons["Pointer"].click()
        self.assertTrue(self.tools.brush_radius.isHidden())

    def test_sphere_placement_is_explicit_contextual_and_hag_aware(self):
        placements = []
        self.tools.spherePlacementChanged.connect(lambda axis, height: placements.append((axis,height)))
        self.assertTrue(self.tools.sphere_height.isHidden())
        self.tools.setSpherePlacement("HeightAboveGround", 12.5, True)
        self.tools.buttons["Sphere"].click()
        self.assertFalse(self.tools.sphere_height.isHidden())
        self.assertEqual((self.tools.sphereAxis(), self.tools.sphereHeight()),
                         ("HeightAboveGround", 12.5))
        self.tools.sphere_height.setValue(13)
        self.assertEqual(placements[-1], ("HeightAboveGround", 13.0))
        self.tools.setSpherePlacement("HeightAboveGround", 13, False)
        self.assertEqual(self.tools.sphereAxis(), "Z")
        self.assertIn("not camera depth", self.tools.sphere_height.toolTip())
        self.tools.sphere_height.lineEdit().setText("14.")
        with patch.object(self.tools.sphere_height, "hasFocus", return_value=True):
            self.tools.setSpherePlacement("Z", 20, False)
        self.assertEqual(self.tools.sphere_height.lineEdit().text(), "14.")

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


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class SelectionLimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        class Controller(QObject):
            limitsChanged = pyqtSignal()
            brushRadiusChanged = pyqtSignal(float)
            depth_error = LinkedViews.depth_error
            set_depth = LinkedViews.set_depth
            brush_radius = LinkedViews.brush_radius
            set_brush_radius = LinkedViews.set_brush_radius
        self.controller = Controller()
        self.controller.depth = {}
        self.controller.persist = Mock()
        self.view = SimpleNamespace(view_type="OVERVIEW_3D", geometry={})
        self.controller.page = SimpleNamespace(
            workspace=SimpleNamespace(views={"overview": self.view}, active_view_id="overview",
                                      global_filters={}),
            editor=SimpleNamespace(state={"ready": True, "dimensions": ["Z", "HeightAboveGround"]},
                                   busy=False, refresh_controls=Mock()))
        self.limits = SelectionLimits(self.controller)

    def tearDown(self):
        self.limits.deleteLater()
        self.app.processEvents()

    def test_full_column_default_has_no_invented_height_limits(self):
        self.assertEqual(self.limits.mode.currentText(), "Full column")
        self.assertEqual(self.controller.depth, {})
        self.assertTrue(self.limits.minimum.isHidden())

    def test_hag_limits_are_shared_between_views(self):
        other = SelectionLimits(self.controller, "overview")
        self.limits.mode.setCurrentIndex(self.limits.mode.findData("hag_filter"))
        self.limits.minimum.setValue(8)
        self.limits.maximum.setValue(18)
        self.assertEqual(self.controller.depth, {"hag_filter": [8, 18]})
        self.assertEqual(other.minimum.value(), 8)
        self.assertEqual(other.maximum.value(), 18)
        self.assertGreater(self.limits.mode.sizeHint().width(),
                           self.limits.mode.fontMetrics().horizontalAdvance(self.limits.mode.currentText()) + 16)
        other.deleteLater()

    def test_invalid_range_is_visible_not_silently_clamped(self):
        self.controller.set_depth({"z_filter": [20, 10]})
        self.assertEqual(self.controller.depth_error, "Minimum exceeds maximum")
        self.assertEqual(self.limits.context.text(), "Minimum exceeds maximum")
        self.assertEqual(self.limits.minimum.value(), 20)

    def test_slice_default_names_corridor_thickness(self):
        self.view.view_type = "VERTICAL_SLICE"
        self.view.geometry = {"thickness": 4}
        self.limits.refresh()
        self.assertEqual(self.limits.mode.currentText(), "Within slice thickness")
        self.assertIn("4 XY units", self.limits.context.text())

    def test_missing_hag_is_not_presented_as_full_column(self):
        self.controller.set_depth({"hag_filter": [8, 18]})
        self.controller.page.editor.state["dimensions"] = ["Z"]
        self.limits.refresh()
        self.assertEqual(self.limits.mode.currentText(), "HAG unavailable")
        self.assertEqual(self.controller.depth_error, "Source has no stored HAG")

    def test_refresh_does_not_replace_unfinished_height_entry(self):
        self.controller.set_depth({"z_filter": [0, 50]})
        self.limits.minimum.lineEdit().setText("Min 12.")
        with patch.object(self.limits.minimum, "hasFocus", return_value=True):
            self.limits.refresh()
        self.assertEqual(self.limits.minimum.lineEdit().text(), "Min 12.")

    def test_brush_radius_is_one_persisted_linked_view_setting(self):
        values = []
        self.controller.brushRadiusChanged.connect(values.append)
        self.controller.set_brush_radius(3.25)
        self.assertEqual(self.controller.page.workspace.global_filters["brush_radius"], 3.25)
        self.assertEqual(self.controller.brush_radius, 3.25)
        self.assertEqual(values, [3.25])
        self.controller.persist.assert_called_once_with()
        self.controller.set_brush_radius(float("nan"))
        self.assertEqual(self.controller.brush_radius, 3.25)


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class PointAppearanceControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.send = Mock()
        self.control = PointAppearance(self.send)

    def tearDown(self):
        self.control.deleteLater()
        self.app.processEvents()

    def test_display_commands_do_not_contain_edit_actions(self):
        self.control.style_combo.setCurrentText("Square")
        self.control.size_spin.setValue(8)
        self.send.assert_called_with({"action": "point_display", "style": "Square", "size": 8})
        self.assertTrue(callable(self.control.style))
        self.assertTrue(callable(self.control.size))

    def test_telemetry_sync_does_not_echo_commands(self):
        self.control.sync({"point_style": "Square", "point_size": 6})
        self.assertEqual(self.control.size_spin.value(), 6)
        self.send.assert_not_called()


@unittest.skipIf(QApplication is None, "Requires QGIS Qt")
class ClassVisibilityControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.send = Mock()
        self.control = ClassVisibilityMenu(self.send)

    def tearDown(self):
        self.control.deleteLater()
        self.app.processEvents()

    def test_catalog_menu_toggles_and_isolates_without_edit_commands(self):
        self.control.sync({"observed_classes": [2, 5], "classes": None,
                           "editor": {"effective_classes": {"5": 120}}})
        texts = [action.text() for action in self.control.menu().actions()]
        self.assertIn("Ground (2)", texts)
        self.assertIn("High vegetation (5) | ~120 in view", texts)
        self.control.change(2, False)
        command = self.send.call_args.args[0]
        self.assertEqual(command["action"], "classes")
        self.assertNotIn(2, command["classes"])
        self.control.change(5, False)
        self.assertNotIn(2, self.send.call_args.args[0]["classes"])
        self.assertNotIn(5, self.send.call_args.args[0]["classes"])
        self.control.isolate(5)
        self.send.assert_called_with({"action": "classes", "classes": [5]})
        self.assertNotIn("stage", repr(self.send.call_args_list))

    def test_docked_rows_use_catalog_swatches_and_remove_stale_effective_class(self):
        owner = SimpleNamespace(class_list=QListWidget(), send=Mock())
        self.addCleanup(owner.class_list.deleteLater)
        PointCloudPage.solo_class(owner)
        owner.send.assert_not_called()
        PointCloudPage._observe_classes(owner, [2], None, {"5": 120})
        self.assertEqual(owner.class_list.count(), 2)
        self.assertEqual(owner.class_list.item(0).text(), "Ground (2)")
        self.assertFalse(owner.class_list.item(0).icon().isNull())
        self.assertEqual(owner.class_list.item(1).text(), "High vegetation (5) | ~120 in view")
        PointCloudPage._observe_classes(owner, [2], None, {})
        self.assertEqual(owner.class_list.count(), 1)
        self.assertEqual(owner.class_list.item(0).text(), "Ground (2)")


if __name__ == "__main__":
    unittest.main()
