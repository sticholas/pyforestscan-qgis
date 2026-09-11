import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.point_cloud.selection_product_preflight import (
    SCOPED_EXECUTABLE_PRODUCTS,
    preflight_selection_product,
)
from pyforestscan_qgis.core.point_cloud.selection_product_request import SelectionProductRequest
from pyforestscan_qgis.core.types import ProductType


class SelectionProductPreflightTests(unittest.TestCase):
    def request(self, product=ProductType.CHM, review=False):
        return SelectionProductRequest(
            selection_id="selection-1",
            source_path=Path("forest.laz"),
            source_fingerprint="a" * 64,
            product=product,
            scope_kind="AREA",
            geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 0.0)),
            geometry_crs="EPSG:32604",
            bounds=(0.0, 0.0, 10.0, 8.0),
            vertical_axis="Z",
            z_range=(2.0, 20.0),
            hag_range=None,
            point_count=100,
            output_folder=Path("outputs"),
            review_required=review,
            review_reason="review",
        )

    def test_current_executable_products_pass_the_shared_gate(self):
        self.assertEqual(
            SCOPED_EXECUTABLE_PRODUCTS,
            {ProductType.CHM, ProductType.CANOPY_COVER, ProductType.PAD, ProductType.PAI, ProductType.FHD, ProductType.RUMPLE},
        )
        for product in SCOPED_EXECUTABLE_PRODUCTS:
            report = preflight_selection_product(self.request(product), backend_ready=True, source_exists=True)
            self.assertTrue(report.ready, product.value)
            self.assertEqual(report.execution_status, "READY_FOR_EXECUTION")

    def test_unwired_product_fails_closed_with_product_name(self):
        report = preflight_selection_product(self.request(ProductType.POINT_DENSITY), backend_ready=True, source_exists=True)
        self.assertFalse(report.ready)
        self.assertIn("point_density", " ".join(report.blockers))
        self.assertEqual(report.execution_status, "REVIEW_ONLY")

    def test_missing_backend_and_source_are_actionable(self):
        report = preflight_selection_product(self.request(), backend_ready=False, source_exists=False)
        self.assertFalse(report.ready)
        self.assertIn("PBM backend", " ".join(report.blockers))
        self.assertIn("source does not exist", " ".join(report.blockers))

    def test_scientific_review_remains_a_blocker(self):
        report = preflight_selection_product(self.request(ProductType.CHM, review=True), backend_ready=True, source_exists=True)
        self.assertFalse(report.ready)
        self.assertIn("Scientific review", " ".join(report.blockers))

    def test_pipeline_has_shared_bounded_transport_for_implemented_products(self):
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/core/pipeline.py").read_text()
        self.assertGreaterEqual(source.count("**_selection_request_kwargs(context)"), 6)
