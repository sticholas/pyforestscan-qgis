from __future__ import annotations

import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.lidar_repository_discovery import discover_lidar_repository
from pyforestscan_qgis.core.polygon_source_selection import _read_ept_metadata, _read_ept_metadata_cached
from pyforestscan_qgis.core.source_aware_processing import NativeSource, PlanningCancelled, SourceAwareWorkPlanner, SpatialExtent
from pyforestscan_qgis.core.work_unit_geometry import NormalizedPolygonGeometry, measure_core_polygon_intersection


class Phase32MPrerunPerformanceTests(unittest.TestCase):
    def test_planner_parses_and_validates_polygon_once(self) -> None:
        polygon = "POLYGON ((0 0, 10990 0, 10990 6668, 0 6668, 0 0))"
        source = NativeSource(Path("ept.json"), SpatialExtent(0, 0, 10990, 6668), source_type="ept")
        with patch("pyforestscan_qgis.core.work_unit_geometry.wkt_to_geojson_geometry", wraps=__import__("pyforestscan_qgis.core.polygon_transport", fromlist=["wkt_to_geojson_geometry"]).wkt_to_geojson_geometry) as parser:
            plan = SourceAwareWorkPlanner().plan(repository_kind="ept", sources=(source,), polygon_envelope=source.bounds, processing_crs="EPSG:6635", product="chm", resolution=1, polygon_wkt=polygon)
        self.assertEqual(1, parser.call_count)
        self.assertGreater(len(plan.candidate_work_units), 1)

    def test_normalized_geometry_is_immutable_and_reused(self) -> None:
        polygon = NormalizedPolygonGeometry.from_wkt("MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)), ((20 20, 30 20, 30 30, 20 30, 20 20)))", processing_crs="EPSG:6635")
        self.assertEqual(10, polygon.vertex_count)
        with self.assertRaises(Exception):
            polygon.bounds = (0, 0, 1, 1)
        self.assertTrue(measure_core_polygon_intersection(SpatialExtent(2, 2, 8, 8), polygon).intersects)
        self.assertFalse(measure_core_polygon_intersection(SpatialExtent(11, 11, 19, 19), polygon).intersects)

    def test_10000_vertex_500_extent_stress_does_not_reparse(self) -> None:
        count = 10_000
        points = [(5000 + 4000 * math.cos(index * 2 * math.pi / count), 5000 + 4000 * math.sin(index * 2 * math.pi / count)) for index in range(count)]
        text = "POLYGON ((" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in (*points, points[0])) + "))"
        with patch("pyforestscan_qgis.core.work_unit_geometry.wkt_to_geojson_geometry", wraps=__import__("pyforestscan_qgis.core.polygon_transport", fromlist=["wkt_to_geojson_geometry"]).wkt_to_geojson_geometry) as parser:
            polygon = NormalizedPolygonGeometry.from_wkt(text, processing_crs="EPSG:6635")
            started = time.perf_counter()
            for index in range(500):
                x = (index % 25) * 400
                y = (index // 25) * 400
                measure_core_polygon_intersection(SpatialExtent(x, y, x + 350, y + 350), polygon)
        self.assertEqual(1, parser.call_count)
        self.assertLess(time.perf_counter() - started, 15.0)

    def test_cancellation_stops_candidate_evaluation(self) -> None:
        source = NativeSource(Path("ept.json"), SpatialExtent(0, 0, 5000, 5000), source_type="ept")
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls > 2
        with self.assertRaises(PlanningCancelled):
            SourceAwareWorkPlanner().plan(repository_kind="ept", sources=(source,), polygon_envelope=source.bounds, processing_crs="EPSG:6635", product="chm", resolution=1, polygon_wkt="POLYGON ((0 0, 5000 0, 5000 5000, 0 5000, 0 0))", cancel_callback=cancelled)

    def test_recognized_ept_never_walks_internal_storage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ept.json").write_text('{"bounds":[0,0,0,10,10,1]}', encoding="utf-8")
            (root / "ept-data").mkdir()
            with patch("os.walk", side_effect=AssertionError("recognized EPT must not recurse")):
                report = discover_lidar_repository(root)
        self.assertEqual(1, report.ept_count)
        self.assertEqual(1, report.directories_scanned)
        self.assertEqual(1, report.files_examined)

    def test_ept_metadata_cache_is_keyed_by_size_and_mtime(self) -> None:
        _read_ept_metadata_cached.cache_clear()
        with tempfile.TemporaryDirectory() as folder:
            metadata = Path(folder) / "ept.json"
            metadata.write_text('{"bounds":[0,0,0,10,10,1],"points":4}', encoding="utf-8")
            first = _read_ept_metadata(metadata)
            second = _read_ept_metadata(metadata)
            self.assertEqual(first[0], second[0])
            self.assertEqual(1, _read_ept_metadata_cached.cache_info().hits)
            self.assertEqual(1, _read_ept_metadata_cached.cache_info().misses)

    def test_qgis_worker_uses_serialized_request_not_qgis_geometry(self) -> None:
        pages = (Path(__file__).parents[1] / "pyforestscan_qgis" / "ui" / "pages.py").read_text(encoding="utf-8")
        worker = pages[pages.index("class _PolygonPreflightWorker"):pages.index("class _CatalogBuildWorker")]
        self.assertIn("QThread", pages)
        self.assertNotIn("QgsGeometry", worker)
        self.assertNotIn("QgsProject", worker)
        self.assertIn("prerun_profile.json", worker)


if __name__ == "__main__":
    unittest.main()
