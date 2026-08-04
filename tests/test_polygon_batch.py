"""QGIS-free tests for Phase 27F polygon Batch workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.batch import BatchResult
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
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
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))

        self.assertTrue(report.ready)
        self.assertEqual(len(report.inventory.sources), 1)
        self.assertEqual(len(report.selected_sources), 1)
        self.assertIsNone(report.estimated_point_count)
        self.assertEqual(report.query_result.point_estimate_confidence, "Unavailable")
        self.assertIn("a/ept.json", str(selected_source_paths(report)[0]))
        self.assertIn("Logical inputs: 1", polygon_preflight_text(report))

    def test_polygon_preflight_blocks_no_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [10, 10, 0, 15, 15, 5], "points": 100, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))

        self.assertFalse(report.ready)
        self.assertTrue(any("No LiDAR coverage" in item for item in report.blockers))

    def test_unknown_bounds_warn_and_are_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tile.laz").write_text("", encoding="utf-8")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))

        self.assertEqual(len(report.selected_sources), 0)
        self.assertTrue(any("metadata errors" in warning for warning in report.warnings))

    def test_polygon_manifest_records_polygon_and_source_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": 100, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))
            path = write_polygon_batch_manifest(report)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(path.name, POLYGON_MANIFEST_NAME)
        self.assertEqual(payload["mode"], "polygon_area_processing")
        self.assertEqual(len(payload["sources"]), 1)
        self.assertIn("wkt", payload["polygon"])

    def test_execute_polygon_batch_uses_logical_ept_without_staging_nodes(self) -> None:
        class Result:
            def __init__(self, path: Path) -> None:
                self.output_path = path

        class FakeAdapter:
            def create_chm(self, request):
                Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(request.output_path).write_text("chm", encoding="utf-8")
                self.last_request = request
                return Result(Path(request.output_path))

            def normalize_heights(self, request):
                raise AssertionError("EPT logical execution must not stage node LAZ files through QGIS Python")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ept.json").write_text(json.dumps({"bounds": [0, 0, 0, 5, 5, 5], "points": 100, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))
            fake_adapter = FakeAdapter()
            result = execute_polygon_batch(report, adapter=fake_adapter)

        self.assertEqual(result.title, "PyForestScan Polygon Batch")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].dataset_path.name, "ept.json")
        self.assertIn("POLYGON", fake_adapter.last_request.crop_polygon)
        self.assertIsNotNone(fake_adapter.last_request.polygon_execution_input)
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
        self.assertIn("LiDAR Folder Selection", batch_source)
        self.assertIn("Polygon Selection", batch_source)
        self.assertIn("Refresh Polygon Layers", batch_source)
        self.assertIn("Refresh Catalog Status", batch_source)
        self.assertIn("Build Catalog", batch_source)
        self.assertIn("Process LiDAR", batch_source)
        self.assertIn("_build_polygon_batch_request", batch_source)


if __name__ == "__main__":
    unittest.main()
