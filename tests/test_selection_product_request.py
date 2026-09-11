import hashlib
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.selection_processing import selection_scope_from_definition
from pyforestscan_qgis.core.point_cloud.selection_product_request import build_selection_product_request
from pyforestscan_qgis.core.types import ProductType


class SelectionProductRequestTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("forest.laz")
        self.fingerprint = hashlib.sha256(b"source").hexdigest()
        self.scope = selection_scope_from_definition(
            {
                "selection_id": "selection-1",
                "geometry": ((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
                "geometry_crs": "EPSG:32604",
                "scope_kind": "AREA",
                "z_filter": (2.0, 20.0),
            },
            source_path=self.source,
            source_fingerprint=self.fingerprint,
            point_count=1234,
            view_title="Canopy detail",
        )

    def test_request_preserves_authoritative_source_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            request = build_selection_product_request(self.scope, ProductType.CHM, output_folder=folder)
        self.assertEqual(request.product, ProductType.CHM)
        self.assertEqual(request.source_path, self.source)
        self.assertEqual(request.geometry_crs, "EPSG:32604")
        self.assertEqual(request.bounds, (0.0, 0.0, 10.0, 8.0))
        self.assertEqual(request.z_range, (2.0, 20.0))
        self.assertFalse(request.review_required)
        self.assertTrue(request.to_dict()["original_unchanged"])

    def test_profile_request_requires_scientific_review_for_raster_products(self):
        profile = selection_scope_from_definition(
            {
                "selection_id": "profile-1",
                "geometry": ((0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 0.0)),
                "geometry_crs": "EPSG:32604",
                "scope_kind": "PROFILE",
            },
            source_path=self.source,
            source_fingerprint=self.fingerprint,
            point_count=50,
        )
        request = build_selection_product_request(profile, ProductType.CHM, output_folder="outputs")
        self.assertTrue(request.review_required)
        self.assertIn("confirm raster extent", request.review_reason)

    def test_request_serializes_product_and_paths(self):
        payload = build_selection_product_request(self.scope, "point_density", output_folder="outputs").to_dict()
        self.assertEqual(payload["product"], "point_density")
        self.assertEqual(payload["source_path"], "forest.laz")
        self.assertEqual(payload["output_folder"], "outputs")
        self.assertEqual(payload["authority"], "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY")
