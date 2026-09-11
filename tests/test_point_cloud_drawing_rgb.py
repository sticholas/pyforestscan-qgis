"""Run the production, QGIS-free gesture and RGB contracts in Node when available."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DrawingRGBTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for production JavaScript contracts")
    def test_production_contracts(self):
        for name in ("viewer_drawing_rgb_test.cjs", "viewer_gesture_events_test.cjs"):
            result = subprocess.run(["node", str(ROOT / "scripts/testing" / name)],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_editor_no_longer_relies_on_clip_cancellation(self):
        source = (ROOT / "pyforestscan_qgis/viewer/editor.js").read_text()
        self.assertNotIn("clippingTool.startInsertion", source)
        for event in ('"dblclick"', '"contextmenu"', '"Enter"', '"Escape"', '"pointercancel"'):
            self.assertIn(event, source)
        self.assertIn("drawing_state: drawing.state", source)
        self.assertIn('"Circle"', source)
        self.assertIn("circle_center", source)
        self.assertIn("circle_radius", source)
        self.assertIn("insideBrush", source)
        self.assertIn("brush_path", source)
        self.assertIn("brush_radius", source)
        self.assertIn("brush_tolerance", source)
        self.assertIn("profile_brush_path", source)
        self.assertIn("profile_brush_radius", source)
        self.assertNotIn("Brush Select currently works in Overview and Area Detail", source)
        self.assertIn("sphere_center", source)
        self.assertIn("sphere_radius", source)
        self.assertIn("insideSphere", source)
        self.assertIn('command.action === "measurement_tool"', source)
        self.assertIn("getMousePointCloudIntersection", source)
        self.assertIn('"measure_points"', source)
        self.assertIn('"measure_profile_points"', source)
        self.assertIn("renderWorkspaceViews", source)
        self.assertIn("DISPLAY_CONTEXT_ONLY", source)
        self.assertIn("workspace_profile_count", source)
        self.assertIn('"ProfilePath"', source)
        self.assertIn("profileProjected", source)
        self.assertIn('"PFSOriginalX"', source)
        self.assertIn('"PFSOriginalY"', source)
        self.assertIn("pickWithSourceProvenance", source)
        self.assertNotIn("geometry.setAttribute(alias", source)
        self.assertIn("hit.point._pfsPick", source)
        self.assertIn("Linked cursor inspection was skipped.", source)
        self.assertIn('command.action === "linked_cursor"', source)
        self.assertIn('authority:"TRANSIENT_LINKED_CURSOR"', source)
        self.assertIn("linked_cursor_markers", source)

    def test_potree_pick_exposes_cpu_metadata_without_gpu_attributes(self):
        source = (ROOT / "pyforestscan_qgis/viewer/assets/build/potree/potree.js").read_text()
        self.assertGreaterEqual(source.count('Object.defineProperty(point, "_pfsPick"'), 2)
        self.assertIn("sourceDimensions: node.geometryNode.gpsTime", source)
        self.assertIn("enumerable: false", source)

    def test_help_has_fixed_scrollable_footprint(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_widgets.py").read_text()
        self.assertIn("setFixedHeight(self.HEIGHT)", source)
        self.assertIn("WidgetWidth", source)
        self.assertIn("setReadOnly(True)", source)

    def test_profile_renderer_has_visible_axis_and_unit_contract(self):
        html = (ROOT / "pyforestscan_qgis/viewer/viewer.html").read_text()
        script = (ROOT / "pyforestscan_qgis/viewer/viewer.js").read_text()
        for identifier in ("profile-axes", "profile-x-title", "profile-y-title"):
            self.assertIn(identifier, html)
        self.assertIn("Distance along profile", script)
        self.assertIn("Height above ground", script)
        self.assertIn("state.profile_axes", script)
        self.assertIn("updateProfileAxes();\n        fitSource", script)

    def test_view_status_distinguishes_active_display_sample_from_budget(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text()
        self.assertIn("Display sample:", source)
        self.assertIn("Display budget:", source)
        self.assertIn("active_view.title", source)

    def test_editor_acknowledges_one_cooperative_cancel_request(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text()
        self.assertIn("self.cancel_requested = False", source)
        self.assertIn("self.cancel.setEnabled(self.busy and not self.cancel_requested)", source)
        self.assertIn('if action == "cancel" and (not self.busy or self.cancel_requested):', source)
        self.assertIn("Cancellation requested | Waiting for the current bounded source read", source)
        self.assertIn("source points checked", source)

    def test_exact_geometry_metadata_reaches_docked_and_detached_editor(self):
        for name in ("point_cloud_editor.py", "point_cloud_detached.py"):
            source = (ROOT / "pyforestscan_qgis/ui" / name).read_text()
            for key in ("circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
                        "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
                        "sphere_center", "sphere_radius", "sphere_axis", "profile_line",
                        "profile_line_side"):
                self.assertIn(f'"{key}"', source)
            self.assertIn("constraints=constraints, **values", source)
        self.assertIn('lambda: self.send("invert")',
                      (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text())


class ViewerStabilityContractTests(unittest.TestCase):
    def test_selection_activation_preserves_current_camera(self):
        source = (ROOT / "pyforestscan_qgis/viewer/editor.js").read_text()
        self.assertIn("Keep the user's current camera", source)
        self.assertNotIn("context.viewer.setTopView()", source)

    def test_display_appearance_is_workspace_authoritative(self):
        linked = (ROOT / "pyforestscan_qgis/ui/point_cloud_linked_views.py").read_text()
        page = (ROOT / "pyforestscan_qgis/ui/point_cloud_page.py").read_text()
        detached = (ROOT / "pyforestscan_qgis/ui/point_cloud_detached.py").read_text()
        self.assertIn("Renderer telemetry is observational", linked)
        self.assertIn('lod = dict(view.lod)', linked)
        self.assertIn('active_view.lod.get("point_size", 0)', page)
        self.assertIn('lod = dict(view.lod)', detached)
