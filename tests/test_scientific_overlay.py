import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.scientific_overlay import ScientificOverlayPayload, overlay_value_range

class ScientificOverlayTests(unittest.TestCase):
    def test_payload_is_bounded_and_carries_truthful_provenance(self):
        payload = ScientificOverlayPayload("CHM", "Canopy Height Model", "raster_surface", "m", "EPSG:6635", (0.0, 0.0, 2.0, 2.0), 2, 2, (1.0, None, 3.0, 2.0), (1.0, 3.0), -9999.0, "Forest", {"source_fingerprint": "source-sha", "output_path": "chm.tif"}, vertical_semantics="height above ground", band_index=2)
        command = payload.as_command()
        self.assertEqual("scientific_overlay", command["action"])
        self.assertEqual("source-sha", command["overlay"]["provenance"]["source_fingerprint"])
        self.assertEqual(3, payload.valid_value_count)
        self.assertEqual(2, command["overlay"]["band_index"])

    def test_invalid_or_oversized_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            ScientificOverlayPayload("CHM", "CHM", "raster_surface", "m", "", (0, 0, 1, 1), 1, 1, (1,), (1, 1), None, "Viridis", {})
        with self.assertRaises(ValueError):
            ScientificOverlayPayload("CHM", "CHM", "raster_surface", "m", "", (0, 0, 1, 1), 128, 128, tuple([1.0] * (128 * 128)), (1, 1), None, "Viridis", {"source_fingerprint": "x"}, surface_mode="bad")

    def test_value_range_ignores_nodata_and_nonfinite_values(self):
        self.assertEqual((1.0, 4.0), overlay_value_range((None, 1.0, float("nan"), 4.0)))


    def test_viewer_overlay_uses_a_loaded_three_module_without_disabling_the_cloud(self):
        javascript = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn('import("./assets/libs/three.js/three.module.js")', javascript)
        self.assertIn("function applyScientificOverlay", javascript)
        self.assertIn('if (action === "scientific_overlay") applyScientificOverlay(command.overlay);', javascript)
        self.assertIn("overlayWarning(error)", javascript)
        self.assertNotIn("new THREE.", javascript)


    def test_viewer_host_forwards_overlay_clear_commands(self):
        host = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" / "host.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "clear_scientific_overlay":', host)
        self.assertIn('json.dumps({"action": "clear_scientific_overlay"})', host)

    def test_viewer_overlay_is_a_visible_layer_above_the_cloud(self):
        javascript = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn("cloud.boundingBox.max.z + Math.max(.25, cloudHeight * .003)", javascript)
        self.assertIn("depthTest:false", javascript)
        self.assertIn("scientificOverlay.renderOrder = 10000", javascript)
        self.assertIn('display_layer:"above_cloud"', javascript)
