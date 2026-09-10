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
        self.assertIn("sphere_center", source)
        self.assertIn("sphere_radius", source)
        self.assertIn("insideSphere", source)

    def test_help_has_fixed_scrollable_footprint(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_widgets.py").read_text()
        self.assertIn("setFixedHeight(self.HEIGHT)", source)
        self.assertIn("WidgetWidth", source)
        self.assertIn("setReadOnly(True)", source)

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
                        "sphere_center", "sphere_radius", "sphere_axis", "profile_line",
                        "profile_line_side"):
                self.assertIn(f'"{key}"', source)
            self.assertIn("constraints=constraints, **values", source)
        self.assertIn('lambda: self.send("invert")',
                      (ROOT / "pyforestscan_qgis/ui/point_cloud_editor.py").read_text())
