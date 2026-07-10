"""QGIS-free tests for Phase 27F polygon Batch workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.batch import BatchResult
from pyforestscan_qgis.core.polygon_batch import (
    POLYGON_MANIFEST_NAME,
    PolygonBatchRequest,
    execute_polygon_batch,
    polygon_preflight_text,
    run_polygon_batch_preflight,
    selected_source_paths,
    write_polygon_batch_manifest,
)
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.types import HagNormalizationResult, ProductType

ROOT = Path(__file__).resolve().parents[1]


class PolygonBatchPreflightTests(unittest.TestCase):
    def _request(self, root: Path, polygon_wkt: str | None = None) -> PolygonBatchRequest:
        polygon = normalized_selection_from_wkt(polygon_wkt or "POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
        settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
        return PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings)

    def test_polygon_preflight_selects_only_intersecting_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a" ).mkdir()
            (root / "a" / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "srs": {"authority": "EPSG:32610"}, "points": 100}), encoding="utf-8")
            (root / "b" ).mkdir()
            (root / "b" / "ept.json").write_text(json.dumps({"bounds": [10, 10, 0, 15, 15, 5], "srs": {"authority": "EPSG:32610"}, "points": 200}), encoding="utf-8")
            report = run_polygon_batch_preflight(self._request(root))

        self.assertTrue(report.ready)
        self.assertEqual(len(report.inventory.sources), 2)
        self.assertEqual(len(report.selected_sources), 1)
        self.assertEqual(report.estimated_point_count, 100)
        self.assertIn("a/ept.json", str(selected_source_paths(report)[0]))
        self.assertIn("Intersecting sources: 1", polygon_preflight_text(report))

    def test_polygon_preflight_blocks_no_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [10, 10, 0, 15, 15, 5], "points": 100}), encoding="utf-8")
            report = run_polygon_batch_preflight(self._request(root))

        self.assertFalse(report.ready)
        self.assertTrue(any("No discovered LiDAR sources intersect" in item for item in report.blockers))

    def test_unknown_bounds_warn_and_are_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tile.laz").write_text("", encoding="utf-8")
            report = run_polygon_batch_preflight(self._request(root))

        self.assertEqual(len(report.selected_sources), 0)
        self.assertTrue(any("unknown bounds" in warning for warning in report.warnings))

    def test_polygon_manifest_records_polygon_and_source_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": 100}), encoding="utf-8")
            report = run_polygon_batch_preflight(self._request(root))
            path = write_polygon_batch_manifest(report)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(path.name, POLYGON_MANIFEST_NAME)
        self.assertEqual(payload["mode"], "polygon_area_processing")
        self.assertEqual(len(payload["sources"]), 1)
        self.assertIn("wkt", payload["polygon"])

    def test_execute_polygon_batch_clips_before_batch_executor(self) -> None:
        class FakeAdapter:
            def normalize_heights(self, request):
                Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(request.output_path).write_text("clipped", encoding="utf-8")
                self.last_request = request
                return HagNormalizationResult(Path(request.output_path), 12, request.crs, True)

        class FakeExecutor:
            def run(self, request, item_callback=None, job_callback=None, control_callback=None):
                self.request = request
                return BatchResult("id", request.title, "start", "end", request.batch_folder, (), request.batch_folder / "batch_summary.json", request.batch_folder / "batch_summary.csv", request.batch_folder / "batch_summary.html")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": 100}), encoding="utf-8")
            report = run_polygon_batch_preflight(self._request(root))
            fake_adapter = FakeAdapter()
            fake_executor = FakeExecutor()
            result = execute_polygon_batch(report, adapter=fake_adapter, executor=fake_executor)

        self.assertEqual(result.title, "PyForestScan Polygon Batch")
        self.assertEqual(len(fake_executor.request.datasets), 1)
        self.assertTrue(str(fake_executor.request.datasets[0]).endswith("_polygon_clip.laz"))
        self.assertIn("POLYGON", fake_adapter.last_request.crop_polygon)
        self.assertIsNotNone(fake_adapter.last_request.bounds)


class PolygonBatchUiStaticTests(unittest.TestCase):
    def test_dataset_no_longer_contains_polygon_folder_workflow(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        dataset_start = source.index("class DatasetPage")
        batch_start = source.index("class BatchPage")
        dataset_source = source[dataset_start:batch_start]
        self.assertNotIn("Process Folder by Polygon", dataset_source)
        self.assertNotIn("polygon_lidar_folder_edit", dataset_source)
        self.assertNotIn("Polygon source", dataset_source)

    def test_batch_contains_mode_selector_and_polygon_controls(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        batch_source = source[source.index("class BatchPage"):]
        self.assertIn("Standard File Batch", batch_source)
        self.assertIn("Polygon Area Processing", batch_source)
        self.assertIn("Refresh Polygon Layers", batch_source)
        self.assertIn("Refresh LiDAR Folder", batch_source)
        self.assertIn("Run Polygon Batch", batch_source)
        self.assertIn("_build_polygon_batch_request", batch_source)


if __name__ == "__main__":
    unittest.main()
