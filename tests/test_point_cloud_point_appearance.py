import unittest
from pyforestscan_qgis.core.point_cloud.point_appearance import point_appearance
from pyforestscan_qgis.core.point_cloud.workspace import PointCloudWorkspaceModel


class PointAppearanceTests(unittest.TestCase):
    def test_circular_automatic_is_default(self):
        self.assertEqual(point_appearance(), {"point_style": "Circular", "point_size": 0})

    def test_invalid_size_or_style_cannot_enter_saved_views(self):
        for size in (-1, 17, 1.5, True, "8", float("nan")):
            with self.subTest(size=size), self.assertRaises(ValueError):
                point_appearance("Circular", size)
        with self.assertRaises(ValueError):
            point_appearance("Voxel", 2)

    def test_appearance_round_trips_in_view_local_state(self):
        model = PointCloudWorkspaceModel()
        key = model.register(view_id="overview")
        model.source_fingerprint = "a" * 64
        model.update_view(key, lod={"quality": "Automatic", **point_appearance("Square", 8)})
        restored = PointCloudWorkspaceModel.restore(model.to_dict(), "a" * 64)
        self.assertEqual(restored.views[key].lod["point_size"], 8)
        self.assertEqual(restored.views[key].lod["point_style"], "Square")
        self.assertEqual(restored.global_filters, {})
