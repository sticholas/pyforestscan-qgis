"""QGIS-free tests for adaptive and lazy LiDAR repository indexing."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.adaptive_lidar_indexing import (
    CatalogPerformanceReport,
    FilenameGridProfile,
    IndexBuildCost,
    LidarIndexStrategy,
    LidarPartition,
    audit_persistent_worker_lifecycle,
    choose_index_strategy,
    current_polygon_coverage,
    detect_repository_capabilities,
    format_repository_index_plan,
    read_existing_footprint_index,
    records_from_filename_grid,
    register_existing_footprint_index,
    select_partitions_for_polygon,
    two_pass_full_catalog_plan,
)
from pyforestscan_qgis.core.lidar_catalog import catalog_summary
from pyforestscan_qgis.core.lidar_catalog_models import default_lidar_catalog_path
from pyforestscan_qgis.core.spatial_selection import Bounds2D


def write_ept(path: Path, points: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 5], "points": points, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")


class AdaptiveLidarIndexingTests(unittest.TestCase):
    def test_existing_plugin_catalog_is_preferred_without_header_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = default_lidar_catalog_path(root)
            catalog.parent.mkdir(parents=True, exist_ok=True)
            catalog.touch()
            capabilities = detect_repository_capabilities(root)
            plan = choose_index_strategy(capabilities)

        self.assertEqual(plan.selected_strategy, LidarIndexStrategy.EXISTING_SPATIAL_INDEX)
        self.assertEqual(plan.files_requiring_header_inspection, 0)
        self.assertEqual(plan.expected_build_cost, IndexBuildCost.NONE)
        self.assertIn("Existing PyForestScan SQLite catalog", plan.reason)

    def test_existing_csv_index_can_be_registered_as_catalog_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "tile_001.laz"
            source.write_bytes(b"LASF" + (b"\0" * 371))
            index = root / "footprint_index.csv"
            with index.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["source_path", "xmin", "xmax", "ymin", "ymax", "crs", "point_count", "source_type"])
                writer.writeheader()
                writer.writerow({"source_path": source.name, "xmin": 0, "xmax": 1, "ymin": 2, "ymax": 3, "crs": "EPSG:32610", "point_count": 7, "source_type": "laz"})
            records = read_existing_footprint_index(index, root)
            catalog = register_existing_footprint_index(index, root)
            summary = catalog_summary(catalog, root)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].relative_path, "tile_001.laz")
        self.assertEqual(summary.indexed_count, 1)

    def test_pdal_tile_index_is_recognized_as_existing_spatial_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tile_index.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
            capabilities = detect_repository_capabilities(root)
            plan = choose_index_strategy(capabilities)

        self.assertIsNotNone(capabilities.existing_pdal_tindex)
        self.assertEqual(plan.selected_strategy, LidarIndexStrategy.EXISTING_SPATIAL_INDEX)
        self.assertTrue(plan.requires_user_confirmation)

    def test_ept_directory_is_registered_as_native_source_not_crawled_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_ept(root / "county_ept" / "ept.json")
            (root / "county_ept" / "ept-data" / "0-0-0-0.laz").parent.mkdir(parents=True)
            (root / "county_ept" / "ept-data" / "0-0-0-0.laz").write_bytes(b"not inspected")
            capabilities = detect_repository_capabilities(root)
            plan = choose_index_strategy(capabilities)

        self.assertEqual(capabilities.ept_roots, (root / "county_ept" / "ept.json",))
        self.assertEqual(plan.selected_strategy, LidarIndexStrategy.NATIVE_HIERARCHICAL_SOURCE)
        self.assertEqual(plan.sources_to_register, capabilities.ept_roots)

    def test_filename_grid_profile_requires_approval_and_crs(self) -> None:
        profile = FilenameGridProfile("utm_1k", r"tile_(?P<x>\d+)_(?P<y>\d+)\.laz", "x", "y", 1000, 1000, crs="EPSG:32610")
        with self.assertRaises(ValueError):
            profile.derive_bounds("tile_500000_4600000.laz")
        approved = FilenameGridProfile("utm_1k", profile.filename_regex, "x", "y", 1000, 1000, crs="EPSG:32610", approved=True)
        bounds = approved.derive_bounds("tile_500000_4600000.laz")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tile = root / "tile_500000_4600000.laz"
            tile.write_bytes(b"LASF")
            records = records_from_filename_grid(root, [tile], approved)

        self.assertEqual(bounds, Bounds2D(500000, 4600000, 501000, 4601000))
        self.assertEqual(records[0].source_crs, "EPSG:32610")
        self.assertEqual(records[0].header_signature, "filename-grid:utm_1k")

    def test_partitioned_lazy_selects_polygon_relevant_partitions(self) -> None:
        partitions = (
            LidarPartition("a", "a", Bounds2D(0, 0, 10, 10), "EPSG:32610", source_count_estimate=5, index_status="ready"),
            LidarPartition("b", "b", Bounds2D(20, 20, 30, 30), "EPSG:32610", source_count_estimate=5),
        )
        selected = select_partitions_for_polygon(partitions, Bounds2D(5, 5, 6, 6))
        capabilities = detect_repository_capabilities(Path(tempfile.gettempdir()), partitions=partitions)
        plan = choose_index_strategy(capabilities, polygon_bounds=Bounds2D(5, 5, 6, 6), requested=LidarIndexStrategy.PARTITIONED_LAZY)

        self.assertEqual(selected, (partitions[0],))
        self.assertEqual(plan.partitions_to_index, (partitions[0],))
        self.assertEqual(plan.files_avoided, 1)
        self.assertEqual(current_polygon_coverage(selected), 100.0)

    def test_two_pass_catalog_plan_makes_polygon_queries_available_after_spatial_pass(self) -> None:
        plan = two_pass_full_catalog_plan()
        self.assertTrue(plan.polygon_queries_allowed_after_pass1)
        self.assertIn("xmin", plan.pass1_fields)
        self.assertIn("point_count", plan.pass2_fields)

    def test_performance_report_and_persistent_worker_audit_surface_bottlenecks(self) -> None:
        report = CatalogPerformanceReport(
            LidarIndexStrategy.FULL_HEADER_CATALOG,
            "flat_laz",
            "network",
            traversal_rate=1000,
            header_rate=12,
            sqlite_write_rate=250,
        )
        ok, message = audit_persistent_worker_lifecycle(100, 1)
        bad, bad_message = audit_persistent_worker_lifecycle(100, 100)

        self.assertEqual(report.dominant_bottleneck, "header decoding")
        self.assertTrue(ok)
        self.assertIn("persistent", message)
        self.assertFalse(bad)
        self.assertIn("one process per file", bad_message)

    def test_plan_format_includes_strategy_cost_and_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index = root / "footprint_index.geojson"
            index.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
            plan = choose_index_strategy(detect_repository_capabilities(root))
            text = format_repository_index_plan(plan)

        self.assertIn("Strategy: existing_spatial_index", text)
        self.assertIn("Expected build cost: low", text)
        self.assertIn("Confirmation required", text)

    def test_static_batch_ui_exposes_adaptive_indexing_controls(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        batch = source[source.index("class BatchPage"):]
        self.assertIn("Preview Setup Method", batch)
        self.assertIn("Prepare Repository", batch)
        self.assertIn("Scan File Headers", batch)
        self.assertIn("Use an Existing Footprint Index", batch)
        self.assertIn("Preview Setup Method checks the repository lightly", batch)


if __name__ == "__main__":
    unittest.main()
