import unittest
from pathlib import Path
from pyforestscan_qgis.core.point_cloud.selection_processing import (SelectionProcessingScope, selection_scope_from_definition, selection_product_options)

class SelectionProcessingScopeTests(unittest.TestCase):
    def scope(self, **changes):
        values = {
            "selection_id": "selection-1",
            "source_path": Path("/data/forest.laz"),
            "source_fingerprint": "a" * 64,
            "geometry": ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0), (0.0, 0.0)),
            "geometry_crs": "EPSG:32605",
            "scope_kind": "COLUMN",
            "point_count": 1200,
            "z_range": (2.0, 8.0),
        }
        values.update(changes)
        return SelectionProcessingScope(**values)

    def test_scope_keeps_authoritative_identity_and_bounds(self):
        scope = self.scope()
        self.assertEqual((0.0, 0.0, 10.0, 5.0), scope.bounds)
        self.assertEqual("FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY", scope.to_processing_context()["authority"])
        self.assertTrue(scope.to_processing_context()["original_unchanged"])

    def test_scope_summary_names_column_and_height_units(self):
        self.assertIn("Column", self.scope().summary)
        self.assertIn("elevation 2-8", self.scope().summary)

    def test_hag_summary_uses_hag_axis(self):
        scope = self.scope(z_range=None, hag_range=(0.5, 1.5), vertical_axis="HeightAboveGround")
        self.assertIn("HAG 0.5-1.5", scope.summary)
        self.assertEqual((0.5, 1.5), scope.height_range)

    def test_invalid_scope_cannot_be_processed(self):
        with self.assertRaises(ValueError):
            self.scope(geometry=((0, 0), (1, 0), (1, 1), (0, 1)))
        with self.assertRaises(ValueError):
            self.scope(scope_kind="UNKNOWN")

    def test_definition_factory_preserves_view_context(self):
        scope = selection_scope_from_definition({
            "selection_id": "selection-2",
            "geometry": ((1, 2), (4, 2), (4, 6), (1, 6), (1, 2)),
            "geometry_crs": "EPSG:32605",
            "scope_kind": "PROFILE",
            "profile_axis": "HeightAboveGround",
            "hag_filter": (1.0, 3.0),
        }, source_path="/data/profile.laz", source_fingerprint="b" * 64, point_count=44, view_title="Canopy Profile")
        self.assertEqual("Canopy Profile", scope.view_title)
        self.assertEqual("PROFILE", scope.scope_kind)
        self.assertEqual((1.0, 3.0), scope.hag_range)


    def test_product_options_keep_profile_products_visible_with_review_guidance(self):
        scope = self.scope(scope_kind="PROFILE")
        options = selection_product_options(scope)
        statuses = {item.product.value: item.status for item in options}
        self.assertEqual("AVAILABLE", statuses["point_density"])
        self.assertEqual("REVIEW", statuses["chm"])
        self.assertTrue(any("bounded source-space selection" in item.reason for item in options))
