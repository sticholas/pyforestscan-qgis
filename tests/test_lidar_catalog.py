"""QGIS-free tests for indexed LiDAR catalog behavior."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.lidar_catalog import catalog_summary, connect_catalog, query_intersecting_records
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog, iter_lidar_paths
from pyforestscan_qgis.core.lidar_catalog_models import CatalogBuildOptions, CatalogThresholds, default_lidar_catalog_path, stable_root_id
from pyforestscan_qgis.core.lidar_catalog_query import derive_polygon_query_geometry, query_catalog_for_polygon
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, execute_polygon_batch, run_polygon_batch_preflight
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.raster_mask import is_maskable_raster
from pyforestscan_qgis.core.batch import BatchProductSettings, BatchResult
from pyforestscan_qgis.core.types import HagNormalizationResult, ProductType


def write_ept(path: Path, bounds: list[float], points: int = 10, crs: str = "EPSG:32610") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bounds": bounds, "points": points, "srs": {"authority": crs}}), encoding="utf-8")


def write_las_header(path: Path, *, bounds=(0.0, 10.0, 0.0, 20.0, 1.0, 30.0), points: int = 123) -> None:
    header = bytearray(375)
    header[:4] = b"LASF"
    struct.pack_into("<I", header, 107, points)
    struct.pack_into("<ddd", header, 131, 0.01, 0.01, 0.01)
    struct.pack_into("<ddd", header, 155, 0.0, 0.0, 0.0)
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    struct.pack_into("<dddddd", header, 179, xmax, xmin, ymax, ymin, zmax, zmin)
    path.write_bytes(header)


class LidarCatalogTests(unittest.TestCase):
    def test_schema_creation_and_rtree_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "a" / "ept.json", [0, 0, 0, 5, 5, 5], points=100)
            write_ept(root / "b" / "ept.json", [20, 20, 0, 30, 30, 5], points=200)
            result = build_lidar_catalog(root)
            connection = connect_catalog(result.catalog_path)
            try:
                records = query_intersecting_records(connection, stable_root_id(root), 1, 4, 1, 4)
            finally:
                connection.close()

        self.assertEqual(result.indexed_count, 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].point_count, 100)

    def test_streaming_traversal_filters_supported_sources_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.laz").write_text("bad", encoding="utf-8")
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            write_ept(root / "ept" / "ept.json", [0, 0, 0, 1, 1, 1])
            paths = list(iter_lidar_paths(root, options=CatalogBuildOptions(recursive=True)))

        self.assertEqual({path.name for path in paths}, {"a.laz", "ept.json"})

    def test_incremental_update_skips_unchanged_and_marks_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ept = root / "tile" / "ept.json"
            write_ept(ept, [0, 0, 0, 5, 5, 5])
            first = build_lidar_catalog(root)
            second = build_lidar_catalog(root)
            ept.unlink()
            third = build_lidar_catalog(root)
            summary = catalog_summary(first.catalog_path, root)

        self.assertEqual(first.indexed_count, 1)
        self.assertEqual(second.unchanged_count, 1)
        self.assertEqual(third.deleted_count, 1)
        self.assertEqual(summary.deleted_count, 1)

    def test_las_header_bounds_are_indexed_without_point_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las", bounds=(2.0, 8.0, 3.0, 9.0, 1.0, 4.0), points=456)
            result = build_lidar_catalog(root)
            connection = connect_catalog(result.catalog_path)
            try:
                records = query_intersecting_records(connection, stable_root_id(root), 4, 5, 4, 5)
            finally:
                connection.close()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].point_count, 456)
        self.assertEqual(records[0].xmin, 2.0)

    def test_invalid_metadata_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "bad.laz").write_bytes(b"")
            result = build_lidar_catalog(root)
            summary = catalog_summary(result.catalog_path, root)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(summary.error_count, 1)

    def test_automatic_polygon_bounds_and_transformer(self) -> None:
        polygon = normalized_selection_from_wkt("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((10 10, 12 10, 12 12, 10 10)))", "EPSG:4326")
        geometry = derive_polygon_query_geometry(polygon, catalog_crs="EPSG:3857", transformer=lambda x, y: (x + 100, y + 200))

        self.assertEqual(geometry.envelope.xmin, 100.0)
        self.assertEqual(geometry.envelope.ymin, 200.0)
        self.assertEqual(geometry.envelope.xmax, 112.0)
        self.assertEqual(geometry.ept_bounds, ((100.0, 112.0), (200.0, 212.0)))
        self.assertIn("MULTIPOLYGON", geometry.exact_polygon_wkt)

    def test_polygon_preflight_queries_catalog_not_folder_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "hit" / "ept.json", [0, 0, 0, 5, 5, 5], points=100)
            build_lidar_catalog(root)
            # This file appears after catalog build. Normal preflight must not discover it by scanning.
            write_ept(root / "late" / "ept.json", [0, 0, 0, 5, 5, 5], points=100)
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM backend is ready."))

        self.assertTrue(report.ready)
        self.assertEqual(len(report.selected_sources), 1)
        self.assertIn("hit", str(report.selected_sources[0].path))

    def test_missing_catalog_blocks_preflight_with_build_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "hit" / "ept.json", [0, 0, 0, 5, 5, 5])
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM backend is ready."))

        self.assertFalse(report.ready)
        self.assertTrue(any("Build a LiDAR catalog" in item for item in report.blockers))

    def test_ept_receives_bounds_and_local_las_does_not(self) -> None:
        class FakeAdapter:
            def __init__(self):
                self.requests = []
            def normalize_heights(self, request):
                self.requests.append(request)
                Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(request.output_path).write_text("clip", encoding="utf-8")
                return HagNormalizationResult(Path(request.output_path), 1, request.crs, True)

        class FakeExecutor:
            def run(self, request, **_kwargs):
                self.request = request
                return BatchResult("id", request.title, "start", "end", request.batch_folder, (), request.batch_folder / "batch_summary.json", request.batch_folder / "batch_summary.csv", request.batch_folder / "batch_summary.html")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "ept" / "ept.json", [0, 0, 0, 5, 5, 5])
            write_las_header(root / "tile.las", bounds=(0, 5, 0, 5, 0, 2))
            build_lidar_catalog(root)
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM backend is ready."))
            adapter = FakeAdapter()
            execute_polygon_batch(report, adapter=adapter, executor=FakeExecutor())

        by_name = {Path(request.input_path).name: request for request in adapter.requests}
        self.assertIsNotNone(by_name["ept.json"].bounds)
        self.assertIsNone(by_name["tile.las"].bounds)
        self.assertIn("POLYGON", by_name["tile.las"].crop_polygon)

    def test_query_threshold_warning_and_default_catalog_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "a" / "ept.json", [0, 0, 0, 5, 5, 5])
            write_ept(root / "b" / "ept.json", [0, 0, 0, 5, 5, 5])
            build_lidar_catalog(root)
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
            result = query_catalog_for_polygon(default_lidar_catalog_path(root), root, polygon, thresholds=CatalogThresholds(max_candidates_per_run=1))

        self.assertEqual(len(result.records), 1)
        self.assertTrue(any("maximum candidate threshold" in warning for warning in result.warnings))

    def test_raster_mask_helpers_identify_geotiffs(self) -> None:
        self.assertTrue(is_maskable_raster(Path("chm.tif")))
        self.assertTrue(is_maskable_raster(Path("pad.tiff")))
        self.assertFalse(is_maskable_raster(Path("rumple.csv")))


if __name__ == "__main__":
    unittest.main()
