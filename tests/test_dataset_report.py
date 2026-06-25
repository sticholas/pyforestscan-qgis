"""Tests for Dataset Explorer report generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.dataset_report import (
    build_dataset_explorer_report,
    render_html_report,
    render_json_report,
    write_csv_summary,
    write_html_report,
    write_json_report,
)
from pyforestscan_qgis.core.types import (
    Bounds3D,
    ClassificationCount,
    DatasetFormat,
    DatasetInspection,
    DatasetSource,
)


def make_inspection(
    dimensions: tuple[str, ...] = (
        "X",
        "Y",
        "Z",
        "Classification",
        "Intensity",
        "Red",
        "Green",
        "Blue",
        "GpsTime",
    ),
    classifications: tuple[ClassificationCount, ...] = (
        ClassificationCount(2, 100),
        ClassificationCount(5, 240),
    ),
    crs: str | None = "EPSG:32610",
    point_format: str | None = "7",
    density: float | None = 2.0,
) -> DatasetInspection:
    """Create a small typed inspection object for report tests."""
    return DatasetInspection(
        source=DatasetSource(Path("plot.las"), DatasetFormat.LAS),
        point_count=340,
        bounds=Bounds3D(0.0, 10.0, 0.0, 10.0, 1.0, 28.0),
        crs=crs,
        dimensions=dimensions,
        classification_summary=classifications,
        point_format=point_format,
        estimated_density=density,
        supported_products=(),
        metadata_source="test",
    )


class DatasetReportTests(unittest.TestCase):
    """Dataset Explorer report model and rendering tests."""

    def test_ready_dataset_report_marks_products_with_warnings_until_hag_exists(self) -> None:
        report = build_dataset_explorer_report(make_inspection())

        statuses = {product.product.value: product.status for product in report.products}
        self.assertEqual(statuses["chm"], "Warning")
        self.assertIn("NO_HEIGHT_ABOVE_GROUND", {warning.code for warning in report.warnings})
        self.assertTrue(report.has_color)
        self.assertTrue(report.has_gps_time)
        self.assertTrue(report.has_intensity)

    def test_missing_core_dimensions_reports_unavailable_products(self) -> None:
        report = build_dataset_explorer_report(
            make_inspection(
                dimensions=("X", "Y"),
                classifications=(),
                crs=None,
                point_format="99",
                density=0.25,
            )
        )

        warning_codes = {warning.code for warning in report.warnings}
        self.assertIn("UNKNOWN_CRS", warning_codes)
        self.assertIn("NO_HEIGHT_DIMENSION", warning_codes)
        self.assertIn("LOW_POINT_DENSITY", warning_codes)
        self.assertIn("UNSUPPORTED_POINT_FORMAT", warning_codes)
        self.assertTrue(all(product.status == "Unavailable" for product in report.products))

    def test_report_renderers_create_json_csv_and_html(self) -> None:
        report = build_dataset_explorer_report(make_inspection())
        json_text = render_json_report(report)
        html_text = render_html_report(report)

        payload = json.loads(json_text)
        self.assertEqual(payload["dataset"]["format"], "las")
        self.assertIn("Supported PyForestScan Products", html_text)

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            json_path = write_json_report(report, output_dir / "report.json")
            csv_path = write_csv_summary(report, output_dir / "report.csv")
            html_path = write_html_report(report, output_dir / "report.html")

            self.assertTrue(json_path.is_file())
            self.assertTrue(csv_path.is_file())
            self.assertTrue(html_path.is_file())
            self.assertIn("section,name,value,status,message", csv_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
