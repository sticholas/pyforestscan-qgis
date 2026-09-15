import unittest
from pathlib import Path


class SelectionNavigationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.source = (self.root / "pyforestscan_qgis/viewer/editor.js").read_text()

    def test_activation_preserves_projection_and_camera(self):
        self.assertNotIn("setCameraMode(Potree.CameraMode.ORTHOGRAPHIC)", self.source)
        self.assertIn("Selection activation never owns the camera", self.source)
        self.assertIn("drawingCamera = null", self.source)

    def test_space_navigation_keeps_tool_armed(self):
        self.assertIn('event.code === "Space"', self.source)
        self.assertIn("navigationOverride", self.source)
        self.assertIn('context.viewer.inputHandler.enabled = true', self.source)
        self.assertIn('event.code !== "Space" || !navigationOverride', self.source)

    def test_current_camera_is_captured_for_each_selection_gesture(self):
        self.assertIn('drawingCamera = context.viewer.scene.getActiveCamera().clone()', self.source)
        self.assertIn('if (navigationOverride) return;', self.source)

    def test_selection_help_explains_navigation_and_modifiers(self):
        tools = (self.root / "pyforestscan_qgis/ui/point_cloud_tools.py").read_text()
        self.assertIn("Hold Space", tools)
        self.assertIn("wheel zoom remains available", tools)
        self.assertIn("Shift adds and Alt subtracts", tools)


if __name__ == "__main__":
    unittest.main()
