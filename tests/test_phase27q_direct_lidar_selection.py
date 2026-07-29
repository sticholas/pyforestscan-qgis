"""Phase 27Q direct polygon-to-LiDAR selection tests."""

from __future__ import annotations

import json
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.direct_lidar_selection import DirectLidarFolderSelector, compare_selection_methods
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
from pyforestscan_qgis.core.lidar_catalog_integrity import assign_repository_crs_override
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight, write_polygon_batch_manifest
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.types import ProductType


def write_las_header(path: Path, *, bounds=(0.0, 10.0, 0.0, 10.0, 0.0, 1.0), points: int = 100) -> None:
    header = bytearray(375)
    header[:4] = b"LASF"
    struct.pack_into("<I", header, 107, points)
    struct.pack_into("<ddd", header, 131, 0.01, 0.01, 0.01)
    struct.pack_into("<ddd", header, 155, 0.0, 0.0, 0.0)
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    struct.pack_into("<dddddd", header, 179, xmax, xmin, ymax, ymin, zmax, zmin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)


class Phase27QDirectSelectionTests(unittest.TestCase):
    def test_direct_selection_returns_real_overlapping_paths_with_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hit = root / "a" / "hit.las"
            miss = root / "b" / "miss.laz"
            write_las_header(hit, bounds=(0, 10, 0, 10, 0, 1))
            write_las_header(miss, bounds=(20, 30, 20, 30, 0, 1))
            polygon = normalized_selection_from_wkt("POLYGON ((5 5, 8 5, 8 8, 5 8, 5 5))", "EPSG:6635")
            result = DirectLidarFolderSelector().select(root, polygon, repository_crs_override="EPSG:6635")
            self.assertTrue(result.intersecting_source_paths[0].exists())

        self.assertTrue(result.ready)
        self.assertEqual(result.discovered_file_count, 2)
        self.assertEqual(result.intersecting_source_paths, (hit,))

    def test_direct_selection_handles_edge_touch_and_missing_crs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tile = root / "tile.las"
            write_las_header(tile, bounds=(0, 10, 0, 10, 0, 1))
            polygon = normalized_selection_from_wkt("POLYGON ((10 2, 12 2, 12 4, 10 4, 10 2))", "EPSG:6635")
            missing = DirectLidarFolderSelector().select(root, polygon)
            selected = DirectLidarFolderSelector().select(root, polygon, repository_crs_override="EPSG:6635")

        self.assertFalse(missing.ready)
        self.assertIn("coordinate system is unknown", " ".join(missing.blockers))
        self.assertTrue(selected.ready)
        self.assertEqual(selected.intersecting_source_paths, (tile,))

    def test_catalog_zero_with_direct_hit_uses_fallback_in_preflight_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tile = root / "tile.las"
            write_las_header(tile, bounds=(0, 10, 0, 10, 0, 1))
            catalog_result = build_lidar_catalog(root)
            assign_repository_crs_override(catalog_result.catalog_path, root, "EPSG:6635", assigned_by="test")
            connection = sqlite3.connect(str(catalog_result.catalog_path))
            try:
                connection.execute("DELETE FROM lidar_source_bounds")
                connection.commit()
            finally:
                connection.close()
            polygon = normalized_selection_from_wkt("POLYGON ((5 5, 8 5, 8 8, 5 8, 5 5))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            report = run_polygon_batch_preflight(
                PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings, catalog_path=catalog_result.catalog_path, repository_crs_override="EPSG:6635"),
                backend_probe=lambda: (True, "PBM ready"),
            )
            manifest = write_polygon_batch_manifest(report)
            payload = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertTrue(report.ready)
        self.assertEqual(report.selection_method, "direct_header_scan")
        self.assertEqual([source.path for source in report.selected_sources], [tile])
        self.assertEqual(payload["selection_method"], "direct_header_scan")
        self.assertEqual(payload["direct_selection"]["intersecting_source_paths"], [str(tile)])

    def test_compare_selection_methods_reports_catalog_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tile = root / "tile.las"
            write_las_header(tile, bounds=(0, 10, 0, 10, 0, 1))
            polygon = normalized_selection_from_wkt("POLYGON ((5 5, 8 5, 8 8, 5 8, 5 5))", "EPSG:6635")
            direct = DirectLidarFolderSelector().select(root, polygon, repository_crs_override="EPSG:6635")
            comparison = compare_selection_methods(direct, ())

        self.assertTrue(comparison.catalog_selection_failure)
        self.assertEqual(comparison.selected_by_direct_only, (tile,))

    def test_audit_script_compares_selection_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tile = root / "tile.las"
            write_las_header(tile, bounds=(0, 10, 0, 10, 0, 1))
            polygon = "POLYGON ((5 5, 8 5, 8 8, 5 8, 5 5))"
            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/audit_polygon_lidar_selection.py",
                    "--repository",
                    str(root),
                    "--polygon",
                    polygon,
                    "--polygon-crs",
                    "EPSG:6635",
                    "--repository-crs",
                    "EPSG:6635",
                    "--direct-scan",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)

        self.assertEqual(payload["direct"]["intersecting_source_paths"], [str(tile)])
        self.assertEqual(payload["preflight"]["selection_method"], "direct_header_scan")


if __name__ == "__main__":
    unittest.main()
