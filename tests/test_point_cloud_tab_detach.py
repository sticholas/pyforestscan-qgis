"""Actual Qt event tests; headless tiers skip when QGIS Qt is unavailable."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, Qt, QObject, pyqtSignal
    from qgis.PyQt.QtGui import QMouseEvent
    from qgis.PyQt.QtWidgets import QApplication, QListWidget, QMessageBox, QMenu
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
    def test_linked_view_menu_exposes_compact_saved_viewpoint_actions(self):
        source = (Path(__file__).parents[1]/"pyforestscan_qgis"/"ui"/
                  "point_cloud_linked_views.py").read_text(encoding="utf-8")
        for label in ("Save Current Viewpoint...", "Open Saved Viewpoint...",
                      "Remove Saved Viewpoint...", "Rename Active View...",
                      "Linked Views", "Scene overlays", "Current selection",
                      "Measurements", "Linked markers"):
            self.assertIn(label, source)

    def test_scene_visibility_updates_only_active_view_and_its_renderer(self):
        from pyforestscan_qgis.core.point_cloud.workspace import (
            AreaGeometry, PointCloudWorkspaceModel, ViewType)
        from dataclasses import asdict
        model = PointCloudWorkspaceModel()
        model.register(view_id="overview")
        detail = model.register(ViewType.AREA_DETAIL, "Crown Detail",
            geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (1,2), 30, 30)))
        model.activate(detail)
        worker = Mock()
        page = SimpleNamespace(workspace=model, status=Mock())
        owner = SimpleNamespace(page=page, scene_actions={
            "selection":SimpleNamespace(text=lambda:"Current selection")},
            view_worker=lambda key:worker if key == detail else None, persist=Mock(),
            active=lambda:model.views[model.active_view_id])
        LinkedViews.set_scene_visibility(owner, "selection", False)
        self.assertTrue(model.views["overview"].scene_visibility["selection"])
        self.assertFalse(model.views[detail].scene_visibility["selection"])
        worker.send.assert_called_once_with({"action":"scene_visibility",
            "visibility":{"selection":False,"measurements":True,"annotations":True}})
        owner.persist.assert_called_once()

    def test_dynamic_linked_view_menu_lists_named_views_and_window_state(self):
        from pyforestscan_qgis.core.point_cloud.workspace import (
            AreaGeometry, PointCloudWorkspaceModel, ViewType)
        from dataclasses import asdict
        model = PointCloudWorkspaceModel()
        model.register(title="3D Overview", view_id="overview")
        detail = model.register(ViewType.AREA_DETAIL, "Crown Detail",
            geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (1,2), 30, 30)))
        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        scene_menu = QMenu()
        self.addCleanup(scene_menu.deleteLater)
        scene_actions = {key:scene_menu.addAction(key) for key in (
            "selection", "measurements", "annotations")}
        for action in scene_actions.values():
            action.setCheckable(True)
        detached = Mock()
        detached.isActiveWindow.return_value = False
        owner = SimpleNamespace(page=SimpleNamespace(workspace=model),
            linked_views_menu=menu, detached={detail:detached},
            scene_actions=scene_actions, active=lambda:model.views[model.active_view_id],
            refresh_viewpoint_actions=Mock(), open_linked_view=Mock())
        LinkedViews.refresh_view_actions(owner)
        self.assertEqual([action.text() for action in menu.actions()],
                         ["Overview: 3D Overview", "Area: Crown Detail (window)"])
        self.assertTrue(menu.actions()[0].isChecked())
        menu.actions()[1].trigger()
        owner.open_linked_view.assert_called_once_with(detail)

    def test_open_linked_view_activates_tab_or_raises_detached_window(self):
        from pyforestscan_qgis.core.point_cloud.workspace import PointCloudWorkspaceModel
        model = PointCloudWorkspaceModel()
        model.register(title="3D Overview", view_id="overview")
        page = SimpleNamespace(workspace=model, view_tabs=Mock(), status=Mock())
        page.view_tabs.count.return_value = 1
        page.view_tabs.tabData.return_value = "overview"
        owner = SimpleNamespace(page=page, detached={}, capture=Mock(), open_active=Mock())
        LinkedViews.open_linked_view(owner, "overview")
        owner.capture.assert_called_once()
        owner.open_active.assert_called_once()
        page.view_tabs.setCurrentIndex.assert_called_once_with(0)
        window = Mock()
        owner.detached["overview"] = window
        LinkedViews.open_linked_view(owner, "overview")
        window.show.assert_called_once()
        window.raise_.assert_called_once()
        window.activateWindow.assert_called_once()

    def test_rename_active_view_updates_existing_workspace_authority(self):
        from pyforestscan_qgis.core.point_cloud.workspace import (
            AreaGeometry, PointCloudWorkspaceModel, ViewType)
        from dataclasses import asdict
        model = PointCloudWorkspaceModel()
        model.register(view_id="overview")
        detail = model.register(ViewType.AREA_DETAIL, "Area Detail 1",
            geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (1,2), 30, 30)))
        model.activate(detail)
        page = SimpleNamespace(workspace=model, status=Mock())
        owner = SimpleNamespace(page=page, active=lambda:model.views[model.active_view_id],
                                sync_tabs=Mock(), persist=Mock())
        with patch("pyforestscan_qgis.ui.point_cloud_linked_views.QInputDialog.getText",
                   return_value=("Canopy inspection", True)):
            LinkedViews.rename_active_view(owner)
        self.assertEqual(model.views[detail].title, "Canopy inspection")
        owner.sync_tabs.assert_called_once()
        owner.persist.assert_called_once()

    def test_title_only_changes_update_existing_tabs_and_detached_windows(self):
        from pyforestscan_qgis.core.point_cloud.workspace import (
            AreaGeometry, PointCloudWorkspaceModel, SliceGeometry, ViewType)
        from dataclasses import asdict
        model = PointCloudWorkspaceModel()
        model.register(title="Overview", view_id="Overview")
        model.register(ViewType.AREA_DETAIL, "Area Detail", view_id="Area Detail",
            geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (1,2), 30, 30)))
        model.register(ViewType.VERTICAL_SLICE, "Slice", view_id="Slice",
            geometry=asdict(SliceGeometry((0,0),(10,0),2,"EPSG:32605")))
        window = Mock()
        owner = SimpleNamespace(page=SimpleNamespace(view_tabs=self.tabs, workspace=model),
                                detached={"Slice":window})
        model.rename_view("Area Detail", "Crown Detail")
        model.rename_view("Slice", "Stem Profile")
        LinkedViews.sync_tabs(owner)
        self.assertEqual(self.tabs.tabText(1), "Crown Detail")
        window.setWindowTitle.assert_called_once_with("Stem Profile")

    def test_save_and_open_viewpoint_use_existing_workspace_authority(self):
        from pyforestscan_qgis.core.point_cloud.workspace import PointCloudWorkspaceModel
        model = PointCloudWorkspaceModel()
        model.register(view_id="overview")
        model.accept_editor_snapshot({"ready":True,"source_fingerprint":"a"*64,
                                      "session_id":"session","revision":1})
        camera = {"position":[10.,20.,30.],"yaw":.5,"pitch":-.2,"radius":40.}
        page = SimpleNamespace(_view_state={"camera":camera}, workspace=model,
            editor=SimpleNamespace(state={"source_identity":{"sha256":"a"*64}}),
            status=Mock(), view_tabs=Mock())
        owner = SimpleNamespace(page=page, source_descriptor=lambda:{"sha256":"a"*64},
            active=lambda:model.views[model.active_view_id], persist=Mock(),
            open_active=Mock())
        owner.capture = lambda:model.update_view("overview", camera=camera)
        with patch("pyforestscan_qgis.ui.point_cloud_linked_views.QInputDialog.getText",
                   return_value=("Crown view",True)):
            LinkedViews.save_viewpoint(owner)
        item = next(iter(model.bookmarks.values()))
        self.assertEqual(item.name,"Crown view")
        owner.persist.assert_called_once()
        model.update_view("overview",camera={"position":[1.,2.,3.],"yaw":0.,
            "pitch":0.,"radius":2.})
        owner.choose_viewpoint=lambda _title:item
        page.view_tabs.count.return_value=0
        LinkedViews.open_viewpoint(owner)
        self.assertEqual(model.views["overview"].camera,item.camera)
        owner.open_active.assert_called_once()

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
        self.assertIn("canopy", editor.target_guidance.toolTip())
        editor.code.setValue(2)
        self.assertIn("DTM", editor.target_guidance.toolTip())

    def test_quick_target_changes_proposal_without_staging_an_edit(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        with patch.object(editor, "stage") as stage:
            editor.set_classification_target(9)
        self.assertEqual(editor.code.value(), 9)
        self.assertEqual(editor.classes.currentData(), 9)
        stage.assert_not_called()
        self.assertEqual(len(editor.quick_targets.menu().actions()), 8)
        self.assertTrue(all(not action.icon().isNull()
                            for action in editor.quick_targets.menu().actions()))

    def test_classification_audit_actions_are_contextual_and_nonautomatic(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        actions = [action.text() for action in editor.details_button.menu().actions()]
        self.assertIn("Audit All Classifications", actions)
        self.assertIn("Classification Audit Results", actions)
        self.assertFalse(editor.audit_result_action.isEnabled())

    def test_object_field_discovery_is_explicit_and_results_start_disabled(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        actions = [action.text() for action in editor.object_menu.actions()]
        self.assertIn("Discover Object Fields", actions)
        self.assertIn("Discovery Results", actions)
        self.assertIn("Build Exact Object Catalog...", actions)
        self.assertIn("Set Unassigned Object Value...", actions)
        self.assertIn("Select Object ID...", actions)
        self.assertIn("Previous Object", actions)
        self.assertIn("Next Object", actions)
        self.assertIn("Object Focus", actions)
        self.assertIn("Object Operations", actions)
        operation_actions = [action.text() for action in editor.object_operations_menu.actions()]
        self.assertIn("Create New Object from Selection", operation_actions)
        self.assertIn("Assign Selection to Object ID...", operation_actions)
        self.assertIn("Unassign Selected Points", operation_actions)
        self.assertIn("Choose Portion to Split", operation_actions)
        self.assertIn("Split Selected Portion to New Object", operation_actions)
        self.assertIn("Merge Active Object Into...", operation_actions)
        self.assertFalse(editor.object_results_action.isEnabled())
        self.assertFalse(editor.build_object_catalog_action.isEnabled())
        self.assertFalse(editor.select_object_action.isEnabled())
        self.assertFalse(editor.configure_object_ids_action.isEnabled())
        self.assertFalse(editor.create_object_action.isEnabled())
        self.assertFalse(editor.assign_object_action.isEnabled())
        self.assertFalse(editor.unassign_object_action.isEnabled())
        self.assertFalse(editor.begin_object_split_action.isEnabled())
        self.assertFalse(editor.finish_object_split_action.isEnabled())
        self.assertFalse(editor.cancel_object_split_action.isEnabled())
        self.assertFalse(editor.merge_object_action.isEnabled())
        self.assertFalse(editor.effective_object_audit_action.isEnabled())
        self.assertFalse(editor.effective_object_results_action.isEnabled())
        self.assertFalse(editor.mark_object_reviewed_action.isEnabled())
        self.assertFalse(editor.mark_object_unreviewed_action.isEnabled())
        self.assertFalse(editor.edit_object_note_action.isEnabled())
        self.assertTrue(editor.show_all_objects_action.isChecked())
        self.assertFalse(editor.fade_other_objects_action.isEnabled())
        self.assertFalse(editor.isolate_object_action.isEnabled())

    def test_object_catalog_actions_follow_context_prerequisites(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.viewer_ready = True
        editor.state = {"ready":True, "object_field_discovery":{"candidate_fields":[{"name":"Tree_ID"}]}}
        editor.refresh_controls()
        self.assertTrue(editor.build_object_catalog_action.isEnabled())
        self.assertFalse(editor.select_object_action.isEnabled())
        editor.state["object_catalog"] = {"field":"Tree_ID", "minimum_object_id":1,
            "maximum_object_id":3, "editable_integer_ids":True}
        editor.state["active_object"] = {"field":"Tree_ID", "object_id":2,
                                           "selection_id":"selected"}
        editor.state["selection"] = {"selection_id":"selected", "resolved_point_count":12}
        editor.state["object_id_policy"] = {"field":"Tree_ID", "unassigned_id":0,
            "next_available_object_id":4}
        editor.refresh_controls()
        self.assertTrue(editor.select_object_action.isEnabled())
        self.assertTrue(editor.configure_object_ids_action.isEnabled())
        self.assertTrue(editor.previous_object_action.isEnabled())
        self.assertTrue(editor.next_object_action.isEnabled())
        self.assertTrue(editor.create_object_action.isEnabled())
        self.assertTrue(editor.assign_object_action.isEnabled())
        self.assertTrue(editor.unassign_object_action.isEnabled())
        self.assertTrue(editor.begin_object_split_action.isEnabled())
        self.assertTrue(editor.merge_object_action.isEnabled())
        self.assertTrue(editor.effective_object_audit_action.isEnabled())
        self.assertFalse(editor.effective_object_results_action.isEnabled())
        self.assertTrue(editor.mark_object_reviewed_action.isEnabled())
        self.assertTrue(editor.mark_object_unreviewed_action.isEnabled())
        self.assertTrue(editor.edit_object_note_action.isEnabled())
        self.assertFalse(editor.finish_object_split_action.isEnabled())
        editor.state["object_split_source"] = {"field":"Tree_ID", "object_id":2,
            "original_point_count":12, "source_sha256":"a"*64}
        editor.refresh_controls()
        self.assertTrue(editor.finish_object_split_action.isEnabled())
        self.assertTrue(editor.cancel_object_split_action.isEnabled())
        self.assertTrue(editor.fade_other_objects_action.isEnabled())
        self.assertTrue(editor.isolate_object_action.isEnabled())

    def test_unassigned_object_policy_requires_explicit_confirmation(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.state = {"object_catalog":{"field":"Tree_ID", "editable_integer_ids":True}}
        editor.send = Mock()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getText",
                   return_value=("0", True)), patch(
                   "pyforestscan_qgis.ui.point_cloud_editor.QMessageBox.question",
                   return_value=qt_enum(QMessageBox, "No", "StandardButton")):
            editor.configure_object_ids()
        editor.send.assert_not_called()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getText",
                   return_value=("0", True)), patch(
                   "pyforestscan_qgis.ui.point_cloud_editor.QMessageBox.question",
                   return_value=qt_enum(QMessageBox, "Yes", "StandardButton")):
            editor.configure_object_ids()
        editor.send.assert_called_once_with("configure_object_id_policy", unassigned_id="0")

    def test_create_object_uses_reserved_next_id_only_after_confirmation(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.state = {
            "object_id_policy":{"field":"Tree_ID", "next_available_object_id":9},
            "selection":{"selection_id":"selected", "resolved_point_count":12}}
        editor.send = Mock()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QMessageBox.question",
                   return_value=qt_enum(QMessageBox, "No", "StandardButton")):
            editor.create_object_from_selection()
        editor.send.assert_not_called()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QMessageBox.question",
                   return_value=qt_enum(QMessageBox, "Yes", "StandardButton")):
            editor.create_object_from_selection()
        editor.send.assert_called_once_with("stage_object_id", selection_id="selected", value="9")

    def test_large_object_edit_confirmation_preserves_worker_action(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.busy = True
        editor.pending_action = "stage_object_id"
        editor.send = Mock()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QMessageBox.question",
                   return_value=qt_enum(QMessageBox, "Yes", "StandardButton")):
            editor.update_state({"confirm":True, "count":500000, "fraction":.5,
                "impact":"Large selection", "edit_kind":"OBJECT_ID",
                "command":{"action":"stage_object_id", "selection_id":"selection",
                           "value":"8", "view":{}}})
        editor.send.assert_called_once_with("stage_object_id", selection_id="selection",
                                            value="8", confirmed=True)

    def test_split_and_merge_actions_preserve_authoritative_selection_identity(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.state = {"selection":{"selection_id":"exact", "resolved_point_count":12},
            "object_split_source":{"field":"Tree_ID", "object_id":2},
            "active_object":{"field":"Tree_ID", "object_id":2},
            "object_catalog":{"field":"Tree_ID", "minimum_object_id":1}}
        editor.send = Mock()
        editor.begin_object_split()
        editor.send.assert_called_once_with("begin_object_split", selection_id="exact")
        editor.send.reset_mock()
        editor.finish_object_split()
        editor.send.assert_called_once_with("split_object", selection_id="exact")
        editor.send.reset_mock()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getText",
                   return_value=("1", True)):
            editor.merge_active_object()
        editor.send.assert_called_once_with("merge_object", selection_id="exact",
                                            target_object_id="1")

    def test_object_review_actions_are_session_metadata_commands(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.state = {"selection":{"selection_id":"exact", "resolved_point_count":12},
            "active_object":{"field":"Tree_ID", "object_id":2},
            "current_object_review":{"reviewed":False, "note":"old"}}
        editor.send = Mock()
        editor.set_object_reviewed(True)
        editor.send.assert_called_once_with("set_object_review", selection_id="exact",
                                            reviewed=True)
        editor.send.reset_mock()
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getMultiLineText",
                   return_value=("new note", True)):
            editor.edit_object_note()
        editor.send.assert_called_once_with("set_object_review", selection_id="exact",
                                            note="new note")

    def test_measurement_control_preserves_selection_tool_and_uses_renderer_command(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        self.assertFalse(editor.measurement_button.isEnabled())
        editor.viewer_ready = True
        editor.state = {"ready":True}
        editor.refresh_controls()
        self.assertTrue(editor.measurement_button.isEnabled())
        editor.page = SimpleNamespace(send=Mock(), linked=SimpleNamespace(depth_error=""))
        editor.tool.blockSignals(True)
        editor.tool.setCurrentText("Rectangle")
        editor.tool.blockSignals(False)
        editor.start_measurement()
        editor.page.send.assert_called_with({"action":"measurement_tool"})
        self.assertEqual(editor.tool.currentText(), "Pointer")
        self.assertTrue(editor.measurement_button.isChecked())
        self.assertTrue(editor.summary.text().startswith("Measurement:"))

    def test_area_measurement_reuses_source_polygon_gesture_without_selecting(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.viewer_ready = True
        editor.state = {"ready":True}
        editor.page = SimpleNamespace(send=Mock(), linked=SimpleNamespace(depth_error=""))
        editor.start_area_measurement()
        editor.page.send.assert_called_once_with(
            {"action":"selection_tool", "tool":"Polygon", "purpose":"MEASURE_AREA"})
        self.assertTrue(editor.summary.text().startswith("Area:"))

    def test_vertical_slice_measurement_uses_profile_specific_renderer_contract(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.viewer_ready = True
        editor.state = {"ready":True}
        view = SimpleNamespace(view_type="VERTICAL_SLICE",view_id="slice",
                               title="Vertical Slice 1",geometry={})
        editor.page = SimpleNamespace(send=Mock(),linked=SimpleNamespace(
            depth_error="",active=lambda:view))
        editor.start_measurement()
        editor.page.send.assert_called_once_with(
            {"action":"measurement_tool","kind":"PROFILE_DISTANCE"})
        self.assertTrue(editor.summary.text().startswith("Cross-section:"))

    def test_tree_height_uses_profile_resolver_with_explicit_scientific_purpose(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.viewer_ready = True
        editor.state = {"ready":True}
        view = SimpleNamespace(view_type="VERTICAL_SLICE",view_id="slice",
                               title="Tree Slice",geometry={})
        editor.page = SimpleNamespace(send=Mock(),linked=SimpleNamespace(
            depth_error="",active=lambda:view))
        editor.start_tree_height_measurement()
        editor.page.send.assert_called_once_with(
            {"action":"measurement_tool","kind":"PROFILE_DISTANCE",
             "purpose":"TREE_HEIGHT"})
        self.assertTrue(editor.summary.text().startswith("Tree height:"))

    def test_measurements_broadcast_once_to_all_linked_renderers(self):
        workers = [Mock(), Mock(), Mock()]
        owner = SimpleNamespace(
            page=SimpleNamespace(worker=workers[0]),
            residents=SimpleNamespace(parked={"detail":{"worker":workers[1]}}),
            detached={"slice":SimpleNamespace(worker=workers[2])})
        owner.viewer_workers = lambda: LinkedViews.viewer_workers(owner)
        measurements = [{"measurement_id":"one"}]
        LinkedViews.set_measurements(owner, measurements)
        for worker in workers:
            worker.send.assert_called_once_with(
                {"action":"measurements", "measurements":measurements})

    def test_linked_markers_use_compact_prompt_and_renderer_contract(self):
        editor = EditorPanel(None)
        self.addCleanup(editor.deleteLater)
        editor.viewer_ready = True
        editor.state = {"ready":True}
        editor.page = SimpleNamespace(send=Mock(), linked=SimpleNamespace(depth_error=""))
        with patch("pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getText",
                   return_value=("Crown fork", True)), patch(
                   "pyforestscan_qgis.ui.point_cloud_editor.QInputDialog.getMultiLineText",
                   return_value=("Review in profile", True)):
            editor.start_annotation()
        editor.page.send.assert_called_once_with({"action":"annotation_tool"})
        self.assertEqual(editor.pending_annotation,
                         {"title":"Crown fork", "note":"Review in profile"})
        self.assertTrue(editor.measurement_button.isChecked())

    def test_annotations_broadcast_once_to_all_linked_renderers(self):
        workers = [Mock(), Mock(), Mock()]
        owner = SimpleNamespace(
            page=SimpleNamespace(worker=workers[0]),
            residents=SimpleNamespace(parked={"detail":{"worker":workers[1]}}),
            detached={"slice":SimpleNamespace(worker=workers[2])})
        owner.viewer_workers = lambda: LinkedViews.viewer_workers(owner)
        annotations = [{"annotation_id":"one"}]
        LinkedViews.set_annotations(owner, annotations)
        for worker in workers:
            worker.send.assert_called_once_with(
                {"action":"annotations", "annotations":annotations})

    def test_object_focus_broadcasts_once_to_all_linked_renderers(self):
        workers = [Mock(), Mock(), Mock()]
        page = SimpleNamespace(
            worker=workers[0],
            workspace=SimpleNamespace(global_filters={}),
            editor=SimpleNamespace(
                state={"active_object":{"field":"Tree_ID", "object_id":7},
                       "selection":{"selection_id":"exact", "resolved_point_count":25}},
                summary=Mock(), refresh_controls=Mock()))
        owner = SimpleNamespace(page=page,
            residents=SimpleNamespace(parked={"detail":{"worker":workers[1]}}),
            detached={"slice":SimpleNamespace(worker=workers[2])}, persist=Mock())
        owner.viewer_workers = lambda: LinkedViews.viewer_workers(owner)
        LinkedViews.set_object_focus(owner, "ISOLATE")
        expected = {"action":"object_focus", "mode":"ISOLATE",
                    "scope":"AUTHORITATIVE_ACTIVE_OBJECT_SELECTION",
                    "field":"Tree_ID", "object_id":"7"}
        for worker in workers:
            worker.send.assert_called_once_with(expected)
        self.assertEqual(page.workspace.global_filters["object_focus_mode"], "ISOLATE")
        owner.persist.assert_called_once_with()

    def test_classify_while_selecting_stages_once_only_after_select_snapshot(self):
        value = {"ready":True, "source":"source.laz", "edits":0, "point_count":100,
            "selection":{"selection_id":"selected", "resolved_point_count":12,
                         "classification_counts":[[2,12]]},
            "selection_definitions":[{"selection_mode":"REPLACE"}],
            "classification_audit":{"status":"NO_FLAGS", "source_point_count":100,
                "classification_changed":0, "removed_on_export":0},
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
        self.assertIn("Selected:", owner.summary.setText.call_args.args[0])
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
