"""QGIS-free evidence for the constraints exposed by the inline limits."""
import unittest
from pyforestscan_qgis.core.point_cloud.linked_selection import linked_constraints, selection_limit_values
from pyforestscan_qgis.core.point_cloud.workspace import PointCloudWorkspaceModel


class LimitContractTests(unittest.TestCase):
    def setUp(self):
        self.view = {"view_id": "overview", "title": "Overview",
                     "view_type": "OVERVIEW_3D", "geometry": {}}

    def test_full_column_does_not_inherit_display_height(self):
        values = linked_constraints(self.view, display={"height_filter": [8, 18]})
        self.assertIsNone(values["z_filter"])
        self.assertIsNone(values["hag_filter"])
        self.assertEqual(values["depth_mode"], "FULL_COLUMN")

    def test_explicit_hag_is_part_of_authoritative_definition(self):
        values = linked_constraints(self.view, hag_filter=[8, 18])
        self.assertEqual(values["hag_filter"], [8, 18])
        self.assertEqual(values["depth_mode"], "CUSTOM_DEPTH_RANGE")

    def test_slice_thickness_and_height_limits_intersect(self):
        self.view.update(view_type="VERTICAL_SLICE", geometry={
            "a": [0, 0], "b": [20, 0], "thickness": 4, "crs": "EPSG:6635",
            "vertical_axis": "HeightAboveGround", "vertical_limits": [5, 15]})
        values = linked_constraints(self.view, hag_filter=[8, 18])
        self.assertEqual(values["profile_thickness"], 4)
        self.assertEqual(values["hag_filter"], (8, 15))
        self.assertEqual(values["depth_mode"], "SLICE_CORRIDOR")

    def test_explicit_display_opt_in_intersects_not_replaces(self):
        values = linked_constraints(self.view, z_filter=[10, 20],
                                    select_filtered=True, display={"height_filter": [15, 25]})
        self.assertEqual(values["z_filter"], (15, 20))

    def test_workspace_restores_limits_from_its_existing_shared_state(self):
        model = PointCloudWorkspaceModel()
        model.register(view_id="overview")
        model.source_fingerprint = "a" * 64
        model.global_filters["selection_limits"] = {"hag_filter": [8, 18]}
        restored = PointCloudWorkspaceModel.restore(model.to_dict(), "a" * 64)
        self.assertEqual(restored.global_filters["selection_limits"], {"hag_filter": [8, 18]})

    def test_saved_limits_reject_non_numeric_or_unknown_contracts(self):
        for values in ([], {"bad": [0, 10]}, {"z_filter": [True, 10]},
                       {"hag_filter": [0, float("nan")]}, {"z_filter": ["8", 18]}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                selection_limit_values(values)
        self.assertEqual(selection_limit_values({"z_filter": [20, 10]}),
                         {"z_filter": [20, 10]})
