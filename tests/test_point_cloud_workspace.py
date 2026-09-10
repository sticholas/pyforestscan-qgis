"""Control-plane tests, not claims of live linked-view rendering qualification."""
from dataclasses import asdict
import json
import unittest
from pyforestscan_qgis.core.point_cloud.workspace import (
    PointCloudWorkspaceModel, ViewType, AreaGeometry, SliceGeometry,
    ViewerResourceCoordinator, scene_visibility)


class WorkspaceTests(unittest.TestCase):
    def model(self):
        model = PointCloudWorkspaceModel()
        overview = model.register(view_id="overview")
        model.accept_editor_snapshot({"ready": True, "source_fingerprint": "a"*64,
                                      "session_id": "session-a", "revision": 1})
        return model, overview

    def detail(self, model):
        return model.register(ViewType.AREA_DETAIL, "Area Detail 1",
            geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (1,2), 30, 30)))

    def test_same_authoritative_selection_and_overlay_for_every_view(self):
        model, overview = self.model()
        detail = self.detail(model)
        received = {overview: [], detail: []}
        for view, events in received.items():
            model.subscribe(view, events.append)
        snapshot = {"ready": True, "source_fingerprint": "a"*64, "session_id": "session-a",
                    "selection": {"selection_id": "original-selection", "resolved_point_count": 21402},
                    "revision": 2, "overlay": "one-authoritative-overlay.json"}
        model.accept_editor_snapshot(snapshot)
        self.assertEqual(received[overview][-1], received[detail][-1])
        received[detail][-1]["selection"]["resolved_point_count"] = 1
        self.assertEqual(model.editor_snapshot["selection"]["resolved_point_count"], 21402)

    def test_undo_redo_use_one_managed_owner(self):
        model, overview = self.model()
        detail = self.detail(model)
        commands = []
        model.bind_editor(lambda action, **values: commands.append((action, values)))
        model.command(detail, "undo")
        model.command(overview, "redo")
        self.assertEqual(commands, [("undo", {}), ("redo", {})])

    def test_local_filters_do_not_change_global_filters_or_other_view(self):
        model, overview = self.model()
        detail = self.detail(model)
        model.update_view(detail, display_filters={"classes": [2]})
        self.assertEqual(model.views[overview].display_filters, {})
        self.assertEqual(model.global_filters, {})

    def test_scene_overlays_are_per_view_persistent_and_not_editor_authority(self):
        model, overview = self.model()
        detail = self.detail(model)
        model.update_view(detail, scene_visibility={"selection": False,
            "measurements": True, "annotations": False, "profiles": True})
        self.assertEqual(model.views[overview].scene_visibility, scene_visibility())
        self.assertFalse(model.views[detail].scene_visibility["selection"])
        self.assertFalse(model.views[detail].scene_visibility["annotations"])
        self.assertTrue(model.views[detail].scene_visibility["profiles"])
        self.assertEqual(model.editor_snapshot["source_fingerprint"], "a" * 64)
        restored = PointCloudWorkspaceModel.restore(
            json.loads(json.dumps(model.to_dict())), "a" * 64)
        self.assertEqual(restored.views[detail].scene_visibility,
                         model.views[detail].scene_visibility)

    def test_scene_visibility_rejects_unknown_or_non_boolean_values(self):
        model, overview = self.model()
        with self.assertRaisesRegex(ValueError, "unsupported overlay"):
            model.update_view(overview, scene_visibility={"source": False})
        with self.assertRaisesRegex(ValueError, "true or false"):
            model.update_view(overview, scene_visibility={"selection": 0})

    def test_schema_one_workspace_restores_with_visible_scene_defaults(self):
        model, overview = self.model()
        raw = json.loads(json.dumps(model.to_dict()))
        raw["schema"] = 1
        raw["views"][0].pop("scene_visibility")
        restored = PointCloudWorkspaceModel.restore(raw, "a" * 64)
        self.assertEqual(restored.views[overview].scene_visibility, scene_visibility())

    def test_views_cannot_replace_journal_or_selection(self):
        model, overview = self.model()
        with self.assertRaises(ValueError):
            model.update_view(overview, selection={"sample_indices": [1]})
        detail = self.detail(model)
        model.bind_editor(lambda *args, **kwargs: None)
        with self.assertRaises(NotImplementedError):
            model.command(detail, "select", sample_indices=[1])

    def test_metadata_roundtrip_is_lazy_and_source_bound(self):
        model, overview = self.model()
        detail = self.detail(model)
        model.activate(detail)
        raw = json.loads(json.dumps(model.to_dict()))
        restored = PointCloudWorkspaceModel.restore(raw, "a"*64)
        self.assertEqual(restored.active_view_id, detail)
        self.assertEqual(restored.to_dict(), raw)
        self.assertEqual(restored.editor_snapshot, {})
        with self.assertRaises(ValueError):
            PointCloudWorkspaceModel.restore(raw, "b"*64)

    def test_profile_camera_color_and_point_appearance_roundtrip(self):
        model, _ = self.model()
        profile = model.register(ViewType.VERTICAL_SLICE, "Canopy Profile",
            geometry=asdict(SliceGeometry((0,0),(20,0),4,"EPSG:32605",
                display_projection="PROFILE_DISTANCE")))
        camera = {"position":[10.,0.,25.], "yaw":0., "pitch":0., "radius":18.}
        model.update_view(profile, camera=camera, render_mode="Intensity",
            lod={"quality":"High Detail", "point_style":"Circular", "point_size":5})
        restored = PointCloudWorkspaceModel.restore(
            json.loads(json.dumps(model.to_dict())), "a"*64)
        view = restored.views[profile]
        self.assertEqual(view.camera["position"], [10.,0.,25.])
        self.assertEqual(view.render_mode, "Intensity")
        self.assertEqual(view.lod, {"quality":"High Detail",
                                   "point_style":"Circular", "point_size":5})

    def test_linked_view_names_are_validated_unique_and_persisted(self):
        model, _ = self.model()
        detail = self.detail(model)
        self.assertEqual(model.rename_view(detail, "  Crown review  "), "Crown review")
        self.assertEqual(model.views[detail].title, "Crown review")
        with self.assertRaisesRegex(ValueError, "unique"):
            model.register(ViewType.AREA_DETAIL, "crown REVIEW",
                geometry=asdict(AreaGeometry("SQUARE", "EPSG:32605", (4,5), 10, 10)))
        with self.assertRaisesRegex(ValueError, "1 to 80"):
            model.rename_view(detail, "")
        raw = json.loads(json.dumps(model.to_dict()))
        restored = PointCloudWorkspaceModel.restore(raw, "a"*64)
        self.assertEqual(restored.views[detail].title, "Crown review")

    def test_named_viewpoint_roundtrip_and_activation_restore_exact_camera(self):
        model, _ = self.model()
        detail = self.detail(model)
        camera = {"position":[10.,20.,30.], "yaw":.5, "pitch":-.25, "radius":40.}
        key = model.add_bookmark("Canopy review", detail, camera,
                                 bookmark_id="b"*32)
        model.update_view(detail, camera={"position":[1.,2.,3.], "yaw":0.,
                                          "pitch":0., "radius":5.})
        bookmark = model.activate_bookmark(key)
        self.assertEqual(model.active_view_id, detail)
        self.assertEqual(model.views[detail].camera, bookmark.camera)
        raw = json.loads(json.dumps(model.to_dict()))
        restored = PointCloudWorkspaceModel.restore(raw, "a"*64)
        self.assertEqual(restored.bookmarks[key].name, "Canopy review")
        self.assertEqual(restored.bookmarks[key].camera["position"], (10.,20.,30.))
        self.assertEqual(json.loads(json.dumps(restored.to_dict())),
                         json.loads(json.dumps(model.to_dict())))

    def test_viewpoints_are_bounded_validated_and_removed_with_their_view(self):
        model, overview = self.model()
        camera = {"position":[0.,0.,1.], "yaw":0., "pitch":0., "radius":2.}
        with self.assertRaisesRegex(ValueError, "name"):
            model.add_bookmark("   ", overview, camera)
        with self.assertRaisesRegex(ValueError, "positive radius"):
            model.add_bookmark("Bad camera", overview, {**camera,"radius":0})
        detail = self.detail(model)
        key = model.add_bookmark("Temporary detail", detail, camera)
        model.close_view(detail)
        self.assertNotIn(key, model.bookmarks)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            model.activate_bookmark(key)

    def test_new_source_session_discards_source_bound_viewpoints(self):
        model, overview = self.model()
        model.add_bookmark("Original source", overview,
            {"position":[0.,0.,1.], "yaw":0., "pitch":0., "radius":2.})
        model.accept_editor_snapshot({"ready":True,"source_fingerprint":"b"*64,
                                      "session_id":"session-b","revision":0})
        self.assertEqual(model.bookmarks, {})

    def test_restore_rejects_viewpoint_type_tampering(self):
        model, overview = self.model()
        model.add_bookmark("Overview", overview,
            {"position":[0.,0.,1.],"yaw":0.,"pitch":0.,"radius":2.})
        raw = json.loads(json.dumps(model.to_dict()))
        raw["bookmarks"][0]["view_type"] = "VERTICAL_SLICE"
        with self.assertRaisesRegex(ValueError, "does not match"):
            PointCloudWorkspaceModel.restore(raw,"a"*64)

    def test_object_focus_roundtrips_as_validated_display_state(self):
        model, _ = self.model()
        model.global_filters["object_focus_mode"] = "FADE_OTHERS"
        raw = json.loads(json.dumps(model.to_dict()))
        restored = PointCloudWorkspaceModel.restore(raw, "a"*64)
        self.assertEqual(restored.global_filters["object_focus_mode"], "FADE_OTHERS")
        raw["global_filters"]["object_focus_mode"] = "HIDE_SOURCE"
        with self.assertRaisesRegex(ValueError, "Unknown object focus mode"):
            PointCloudWorkspaceModel.restore(raw, "a"*64)

    def test_new_session_same_source_discards_old_selection(self):
        model, overview = self.model()
        self.detail(model)
        model.accept_editor_snapshot({"ready": True, "source_fingerprint": "a"*64,
                                      "session_id": "session-b", "revision": 0, "selection": None})
        self.assertEqual(set(model.views), {overview})
        self.assertIsNone(model.editor_snapshot["selection"])

    def test_stale_revision_ignored(self):
        model, _ = self.model()
        self.assertFalse(model.accept_editor_snapshot({"ready": True, "source_fingerprint": "a"*64,
                                      "session_id": "session-a", "revision": 0}))

    def test_detach_clears_shared_selection_before_next_source_is_verified(self):
        model, overview = self.model()
        self.detail(model)
        observed = []
        model.subscribe(overview, observed.append)
        model.detach_editor()
        self.assertEqual(observed[-1], {})
        self.assertEqual(model.editor_snapshot, {})
        self.assertEqual(model.source_fingerprint, "")
        self.assertEqual(set(model.views), {overview})

    def test_observer_failure_does_not_break_other_views(self):
        model, overview = self.model()
        detail = self.detail(model)
        received = []
        def callback(snapshot):
            if snapshot.get("revision") == 2:
                raise RuntimeError("One renderer failed")
        model.subscribe(detail, callback)
        model.subscribe(overview, received.append)
        model.accept_editor_snapshot({"ready": True, "source_fingerprint": "a"*64,
                                      "session_id": "session-a", "revision": 2})
        self.assertEqual(received[-1]["revision"], 2)
        self.assertIn(detail, model.observer_errors)

    def test_budget_is_global_inactive_views_suspended(self):
        allocation = ViewerResourceCoordinator().allocations(["a","b","c"], "b",
                       point_budget=2_000_000, available_ram=256_000_000, frame_ms=16)
        self.assertEqual(sum(item["points"] for item in allocation.values()), 2_000_000)
        self.assertTrue(all(allocation[key]["suspended"] for key in ("a","c")))

    def test_slice_coordinates_and_corridor(self):
        geometry = SliceGeometry((0,0), (10,0), 4, "EPSG:32605")
        self.assertEqual(geometry.local(5,1,8), (5,8,1))
        self.assertEqual(geometry.corridor(), ((0,2),(10,2),(10,-2),(0,-2),(0,2)))
        hag = SliceGeometry((0,0),(10,0),4,"EPSG:32605","HeightAboveGround")
        self.assertEqual(hag.local(5,1,100,hag=8), (5,8,1))
        with self.assertRaises(ValueError):
            hag.local(5,1,100)

    def test_invalid_geometry_and_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            SliceGeometry((0,0),(0,0),10,"EPSG:32605")
        with self.assertRaises(ValueError):
            AreaGeometry("SQUARE","EPSG:32605",(0,0),10,20)
        with self.assertRaises(ValueError):
            AreaGeometry("CIRCLE","EPSG:32605",(0,0),radius=-1)

    def test_changing_geometry_retains_view_and_session(self):
        model, overview = self.model()
        detail = self.detail(model)
        model.update_view(detail, geometry=asdict(AreaGeometry("SQUARE","EPSG:32605",(1,2),40,40)))
        self.assertIn(detail, model.views)
        self.assertEqual(model.session_id, "session-a")
