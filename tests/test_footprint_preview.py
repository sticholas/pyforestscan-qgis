"""Tests for Dataset Footprint preview construction."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.dataset_report import DatasetExplorerReport
from pyforestscan_qgis.core.types import Bounds3D
from pyforestscan_qgis.ui.qgis_footprint import preview_from_report


class FootprintPreviewTests(unittest.TestCase):
    """Plain-Python tests for footprint preview values."""

    def test_preview_from_report_builds_extent_area_and_center(self) -> None:
        report = _report(Bounds3D(10.0, 30.0, 100.0, 140.0), "EPSG:32610")

        preview = preview_from_report(report, "plot_a.laz")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual("plot_a", preview.dataset_stem)
        self.assertEqual("PyForestScan Footprint - plot_a", preview.layer_name)
        self.assertEqual(800.0, preview.area)
        self.assertEqual(20.0, preview.center_x)
        self.assertEqual(120.0, preview.center_y)
        self.assertEqual((), preview.warnings)

    def test_preview_warns_when_crs_unknown(self) -> None:
        report = _report(Bounds3D(0.0, 1.0, 0.0, 1.0), None)

        preview = preview_from_report(report, "plot.las")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertIn("CRS is unknown", preview.warnings[0])

    def test_preview_returns_none_for_missing_or_invalid_bounds(self) -> None:
        self.assertIsNone(preview_from_report(_report(None, "EPSG:32610"), "plot.laz"))
        self.assertIsNone(preview_from_report(_report(Bounds3D(5.0, 5.0, 0.0, 1.0), "EPSG:32610"), "plot.laz"))

    def test_ept_json_uses_parent_folder_stem(self) -> None:
        report = _report(Bounds3D(0.0, 2.0, 0.0, 2.0), "EPSG:3857")

        preview = preview_from_report(report, "/data/site/ept.json")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual("site", preview.dataset_stem)


def _report(bounds: Bounds3D | None, crs: str | None) -> DatasetExplorerReport:
    return DatasetExplorerReport(
        title="Dataset Explorer",
        generated_at="2026-01-01T00:00:00+00:00",
        source_path="plot.laz",
        source_format="laz",
        is_remote=False,
        metadata_source="test",
        point_count=100,
        bounds=bounds,
        crs=crs,
        point_format="7",
        dimensions=("X", "Y", "Z"),
        classification_summary=(),
        estimated_density=None,
        height_range=(None, None),
        has_color=False,
        has_gps_time=False,
        has_intensity=False,
        warnings=(),
        products=(),
    )


if __name__ == "__main__":
    unittest.main()
