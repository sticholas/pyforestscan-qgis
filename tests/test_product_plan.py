"""Tests for Product Planner report generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.product_plan import (
    ProductPlanError,
    ProductPlannerRequest,
    build_product_plan,
    load_dataset_explorer_json,
    render_plan_html,
    render_plan_json,
    write_plan_csv,
    write_plan_html,
    write_plan_json,
)
from pyforestscan_qgis.core.types import ProductType


def explorer_payload() -> dict[str, object]:
    """Return a minimal Dataset Explorer JSON payload."""
    return {
        "title": "PyForestScan Dataset Explorer",
        "dataset": {
            "source_path": "plot.laz",
            "format": "laz",
            "is_remote": False,
            "metadata_source": "pdal-pipeline",
        },
        "geometry": {
            "bounds": {
                "min_x": 0.0,
                "max_x": 100.0,
                "min_y": 0.0,
                "max_y": 50.0,
                "min_z": 0.0,
                "max_z": 25.0,
            },
            "crs": "EPSG:32610",
            "estimated_density_points_per_square_unit": 4.0,
            "height_range": {"minimum": 0.0, "maximum": 25.0},
        },
        "point_statistics": {
            "point_count": 20000,
            "point_format": "7",
            "dimensions": ["X", "Y", "Z", "Classification", "HeightAboveGround"],
            "classification_summary": [
                {"classification": 2, "count": 5000},
                {"classification": 5, "count": 15000},
            ],
            "has_color": True,
            "has_gps_time": True,
            "has_intensity": True,
        },
        "warnings": [],
        "supported_products": [
            {"product": "chm", "label": "Canopy Height Model (CHM)", "status": "Available", "reason": "Ready."},
            {"product": "pai", "label": "Plant Area Index (PAI)", "status": "Warning", "reason": "Review bins."},
            {"product": "pad", "label": "Plant Area Density (PAD)", "status": "Unavailable", "reason": "Missing prerequisite."},
        ],
        "recommended_actions": [],
    }


class ProductPlannerTests(unittest.TestCase):
    """Product Planner model and rendering tests."""

    def test_product_plan_validates_feasibility_and_estimates_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "products"
            request = ProductPlannerRequest(
                explorer_report_path=Path(directory) / "dataset_explorer.json",
                requested_products=(ProductType.CHM, ProductType.PAI, ProductType.PAD),
                output_folder=output_dir,
                grid_resolution=2.0,
                height_bin_size=5.0,
                title="Planning test",
            )

            report = build_product_plan(explorer_payload(), request)

        statuses = {item.product: item.plan_status for item in report.products}
        self.assertEqual(statuses[ProductType.CHM], "Ready")
        self.assertEqual(statuses[ProductType.PAI], "Needs review")
        self.assertEqual(statuses[ProductType.PAD], "Blocked")
        self.assertEqual(report.estimated_columns, 50)
        self.assertEqual(report.estimated_rows, 25)
        self.assertEqual(report.estimated_cells, 1250)
        self.assertEqual(report.estimated_height_bins, 5)
        self.assertTrue(any(output.path.name == "chm.tif" for output in report.products[0].outputs))

    def test_product_plan_requires_valid_request(self) -> None:
        request = ProductPlannerRequest(
            explorer_report_path=Path("report.json"),
            requested_products=(),
            output_folder=Path("out"),
            grid_resolution=1.0,
        )

        with self.assertRaises(ProductPlanError):
            build_product_plan(explorer_payload(), request)

    def test_product_plan_loads_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explorer = root / "dataset_explorer.json"
            explorer.write_text(json.dumps(explorer_payload()), encoding="utf-8")
            loaded = load_dataset_explorer_json(explorer)
            request = ProductPlannerRequest(
                explorer_report_path=explorer,
                requested_products=(ProductType.CHM,),
                output_folder=root / "products",
                grid_resolution=1.0,
            )
            report = build_product_plan(loaded, request)
            json_text = render_plan_json(report)
            html_text = render_plan_html(report)
            json_path = write_plan_json(report, root / "product_plan.json")
            csv_path = write_plan_csv(report, root / "product_plan.csv")
            html_path = write_plan_html(report, root / "product_plan.html")

            self.assertIn('"processing_executed": false', json_text)
            self.assertIn("Requested Products", html_text)
            self.assertTrue(json_path.is_file())
            self.assertTrue(csv_path.is_file())
            self.assertTrue(html_path.is_file())
            self.assertIn("section,product,name,value,status,message", csv_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
