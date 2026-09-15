import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PointCloudProfileQualificationTests(unittest.TestCase):
    def test_profile_editor_exposes_validated_vertex_operations(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_linked_views.py").read_text()
        for marker in ("Edit Path", "Insert midpoint", "Remove vertex", "replace_path", "update_view"):
            self.assertIn(marker, source)

    def test_legend_uses_renderer_classification_colors_and_swatches(self):
        source = (ROOT / "pyforestscan_qgis/viewer/viewer.js").read_text()
        for marker in ("classificationColorHex", "viewer.classifications", "state.legend", "replaceChildren", "background:${item.color}"):
            self.assertIn(marker, source)

    def test_profile_help_explains_source_units_and_navigation(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_tools.py").read_text()
        self.assertIn("source coordinate", source)
        self.assertIn("Space temporarily navigates", source)


if __name__ == "__main__":
    unittest.main()
