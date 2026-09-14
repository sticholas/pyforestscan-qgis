"""Phase 27O tests for repository discovery, catalog integrity, and action states."""

from __future__ import annotations

import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.lidar_catalog import connect_catalog, query_intersecting_records
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
from pyforestscan_qgis.core.lidar_catalog_integrity import inspect_catalog_integrity, repair_catalog, source_view_rows
from pyforestscan_qgis.core.lidar_catalog_jobs import CatalogJobProgress, CatalogJobStage, CatalogJobStatus
from pyforestscan_qgis.core.lidar_catalog_models import LidarCatalogRecord, stable_root_id, utc_now_iso
from pyforestscan_qgis.core.lidar_catalog_query import query_catalog_for_polygon
from pyforestscan_qgis.core.lidar_repository_discovery import discover_lidar_repository
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.repository_actions import repository_action_states, repository_setup_recommendation
from pyforestscan_qgis.core.repository_coverage import build_repository_coverage_model
from pyforestscan_qgis.core.repository_diagnostics import repository_diagnostic_payload
from pyforestscan_qgis.core.types import ProductType


def write_ept(path: Path, bounds: list[float], points: int = 10, crs: str = "EPSG:6635") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bounds": bounds, "points": points, "srs": {"authority": crs}}), encoding="utf-8")


def write_las_header(path: Path, *, bounds=(194000.0, 196000.0, 2166000.0, 2170000.0, 1.0, 30.0), points: int = 123) -> None:
    header = bytearray(375)
    header[:4] = b"LASF"
    struct.pack_into("<I", header, 107, points)
    struct.pack_into("<ddd", header, 131, 0.01, 0.01, 0.01)
    struct.pack_into("<ddd", header, 155, 0.0, 0.0, 0.0)
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    struct.pack_into("<dddddd", header, 179, xmax, xmin, ymax, ymin, zmax, zmin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)


class Phase27ORepositoryCatalogTests(unittest.TestCase):
    def test_discovery_counts_nested_sources_and_excludes_ept_internals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "nested" / "A.LAS")
            (root / "nested" / "b.laz").write_bytes(b"LASF")
            (root / "c.copc.laz").write_bytes(b"LASF")
            write_ept(root / "ept" / "ept.json", [0, 0, 0, 1, 1, 1])
            (root / "ept" / "ept-data" / "0-0-0-0.laz").parent.mkdir(parents=True)
            (root / "ept" / "ept-data" / "0-0-0-0.laz").write_bytes(b"LASF")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")

            report = discover_lidar_repository(root)

        self.assertEqual(report.supported_files_found, 4)
        self.assertEqual(report.las_count, 1)
        self.assertEqual(report.laz_count, 1)
        self.assertEqual(report.copc_count, 1)
        self.assertEqual(report.ept_count, 1)
        self.assertNotIn("0-0-0-0.laz", {path.name for path in report.discovered_paths})

    def test_build_writes_identity_and_healthy_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            report = inspect_catalog_integrity(result.catalog_path, root)

        self.assertEqual(report.status, "CRS Assignment Required")
        self.assertEqual(report.source_row_count, 1)
        self.assertEqual(report.rtree_row_count, 1)
        self.assertIsNotNone(report.identity)
        self.assertEqual(report.identity.repository_fingerprint, stable_root_id(root))
        self.assertIsNotNone(report.extent_union)

    def test_invalid_bounds_do_not_create_rtree_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "bad.las", bounds=(0, 0, 0, 0, 0, 0))
            result = build_lidar_catalog(root)
            report = inspect_catalog_integrity(result.catalog_path, root)

        self.assertEqual(report.source_row_count, 1)
        self.assertEqual(report.rtree_row_count, 0)
        self.assertIn("BOUNDS_INVALID", report.skip_reason_counts)

    def test_epsg6635_rtree_overlap_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las", bounds=(194000, 196000, 2166000, 2170000, 0, 5))
            result = build_lidar_catalog(root)
            connection = connect_catalog(result.catalog_path)
            try:
                records = query_intersecting_records(connection, stable_root_id(root), 194858, 195583, 2167140, 2169530)
            finally:
                connection.close()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].relative_path, "tile.las")

    def test_missing_rtree_is_repaired_and_not_reported_as_no_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            connection = sqlite3.connect(str(result.catalog_path))
            try:
                connection.execute("DELETE FROM lidar_source_bounds")
                connection.commit()
            finally:
                connection.close()
            broken = inspect_catalog_integrity(result.catalog_path, root)
            polygon = normalized_selection_from_wkt("POLYGON ((194858 2167140, 195583 2167140, 195583 2169530, 194858 2169530, 194858 2167140))", "EPSG:6635")
            query = query_catalog_for_polygon(result.catalog_path, root, polygon, catalog_crs="EPSG:6635")
            repair = repair_catalog(result.catalog_path, root)
            fixed = inspect_catalog_integrity(result.catalog_path, root)

        self.assertEqual(broken.status, "Unusable")
        self.assertIn("spatial", " ".join(query.warnings).lower())
        self.assertEqual(repair.after.status, "CRS Assignment Required")
        self.assertEqual(fixed.rtree_row_count, 1)

    def test_polygon_preflight_uses_catalog_repair_message_for_broken_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            connection = sqlite3.connect(str(result.catalog_path))
            try:
                connection.execute("DELETE FROM lidar_source_bounds")
                connection.commit()
            finally:
                connection.close()
            polygon = normalized_selection_from_wkt("POLYGON ((194858 2167140, 195583 2167140, 195583 2169530, 194858 2169530, 194858 2167140))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM ready"))

        self.assertFalse(report.ready)
        self.assertTrue(any("Catalog" in item or "spatial bounds" in item for item in report.blockers))
        self.assertFalse(any(item == "No LiDAR coverage was found for this area." for item in report.blockers))

    def test_healthy_catalog_outside_polygon_uses_true_no_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            from pyforestscan_qgis.core.lidar_catalog_integrity import assign_repository_crs_override
            assign_repository_crs_override(result.catalog_path, root, "EPSG:6635", assigned_by="test")
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 2 1, 2 2, 1 2, 1 1))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM ready"))

        self.assertFalse(report.ready)
        self.assertTrue(any("No LiDAR coverage" in item for item in report.blockers))
        self.assertEqual(report.query_result.catalog_integrity_status, "Healthy with validated repository CRS override")

    def test_stale_catalog_root_is_unusable_for_selected_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root_a = Path(tmpdir) / "a"
            root_b = Path(tmpdir) / "b"
            root_a.mkdir()
            root_b.mkdir()
            write_las_header(root_a / "tile.las")
            result = build_lidar_catalog(root_a)
            report = inspect_catalog_integrity(result.catalog_path, root_b)

        self.assertEqual(report.status, "Unusable")
        self.assertFalse(report.spatially_usable)

    def test_action_states_disable_resume_without_paused_job_and_enable_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            connection = sqlite3.connect(str(result.catalog_path))
            try:
                connection.execute("DELETE FROM lidar_source_bounds")
                connection.commit()
            finally:
                connection.close()
            integrity = inspect_catalog_integrity(result.catalog_path, root)
            states = repository_action_states(has_repository=True, repository_readable=True, catalog_exists=True, integrity=integrity)
            paused = CatalogJobProgress("job", CatalogJobStatus.PAUSED, CatalogJobStage.FINALIZING)
            paused_states = repository_action_states(has_repository=True, repository_readable=True, catalog_exists=True, integrity=integrity, latest_job=paused)

        self.assertFalse(states.resume_catalog_build.enabled)
        self.assertIn("No paused", states.resume_catalog_build.disabled_reason)
        self.assertTrue(states.repair_catalog.enabled)
        self.assertTrue(paused_states.resume_catalog_build.enabled)

    def test_source_view_coverage_and_diagnostic_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_las_header(root / "tile.las")
            result = build_lidar_catalog(root)
            rows = source_view_rows(result.catalog_path, root)
            coverage = build_repository_coverage_model(result.catalog_path, root, mode="outline")
            payload = repository_diagnostic_payload(root, result.catalog_path)
            discovery = discover_lidar_repository(root)
            recommendation = repository_setup_recommendation(discovery, inspect_catalog_integrity(result.catalog_path, root))

        self.assertEqual(len(rows), 1)
        self.assertEqual(coverage.mode, "outline")
        self.assertEqual(len(coverage.features), 1)
        self.assertEqual(payload["catalog"]["status"], "CRS Assignment Required")
        self.assertEqual(recommendation[1], "Assign Coordinate System")


if __name__ == "__main__":
    unittest.main()
