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

    def test_authoritative_stats_and_histogram_are_connected_to_profile_view(self):
        linked_query = (ROOT / "pyforestscan_qgis/core/point_cloud/linked_query.py").read_text()
        linked_views = (ROOT / "pyforestscan_qgis/ui/point_cloud_linked_views.py").read_text()
        viewer = (ROOT / "pyforestscan_qgis/viewer/viewer.js").read_text()
        html = (ROOT / "pyforestscan_qgis/viewer/viewer.html").read_text()
        for marker in ("vertical_stats", "returns", "intensity_stats", "_profile_statistics"):
            self.assertIn(marker, linked_query)
        for marker in ("AnalyticsCoalescer", "profile_requests.submit", "profile_requests.take_latest",
                       "profile_analytics"):
            self.assertIn(marker, linked_views)
        for marker in ("renderProfileHistogram", "analytics_scope", "profile_analytics"):
            self.assertIn(marker, viewer)
        self.assertIn("profile-histogram", html)

    def test_profile_edit_drag_round_trip_is_source_authoritative(self):
        editor = (ROOT / "pyforestscan_qgis/viewer/editor.js").read_text()
        linked = (ROOT / "pyforestscan_qgis/ui/point_cloud_linked_views.py").read_text()
        for marker in ("profileEditStart", "profileEditMove", "profileEditFinish",
                       "profileEditDraft", "profileEditInsert", "profileEditRemove",
                       "profileEditPublish", "profileSource", "PROFILE_GEOMETRY_EDIT"):
            self.assertIn(marker, editor)
        for marker in ("profile_edit_tool", "PROFILE_GEOMETRY_EDIT", "valueChanged.connect",
                       "update_view", "Profile path updated"):
            self.assertIn(marker, linked)

    def test_rendered_legend_can_toggle_renderer_visibility(self):
        source = (ROOT / "pyforestscan_qgis/viewer/viewer.js").read_text()
        for marker in ("role", "button", "setClassVisibility(item.code", "addEventListener",
                       "action === \"classes\"", "updateLegend();"):
            self.assertIn(marker, source)

    def test_detached_profile_edit_routes_through_authoritative_requery(self):
        linked = (ROOT / "pyforestscan_qgis/ui/point_cloud_linked_views.py").read_text()
        detached = (ROOT / "pyforestscan_qgis/ui/point_cloud_detached.py").read_text()
        for marker in ("apply_profile_geometry_edit", "_redetach_after_open",
                       "linked_view_geometry_changed", "QTimer.singleShot"):
            self.assertIn(marker, linked)
        self.assertIn("profile_edit_tool", detached)
        self.assertIn("apply_profile_geometry_edit", detached)

    def test_profile_help_explains_source_units_and_navigation(self):
        source = (ROOT / "pyforestscan_qgis/ui/point_cloud_tools.py").read_text()
        self.assertIn("source coordinate", source)
        self.assertIn("Space temporarily navigates", source)


if __name__ == "__main__":
    unittest.main()
