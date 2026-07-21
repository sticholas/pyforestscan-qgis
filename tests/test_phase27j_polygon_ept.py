"""Regression tests for Phase 27J polygon EPT handling and PBM readiness."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.ept_repository import incorrect_ept_catalog_detected, repair_ept_catalog, resolve_ept_selection
from pyforestscan_qgis.core.lidar_catalog import catalog_summary, connect_catalog, upsert_records
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog, iter_lidar_paths
from pyforestscan_qgis.core.lidar_catalog_models import LidarCatalogRecord, default_lidar_catalog_path, move_lidar_catalog_to_local_storage, repository_side_lidar_catalog_path, source_id_for, stable_root_id
from pyforestscan_qgis.core.lidar_catalog_probe import select_lidar_repository_path
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight, polygon_preflight_text
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.types import ProductType
from pyforestscan_qgis.core.batch import BatchProductSettings


def write_ept(path: Path, points: int = 100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bounds": [0, 0, 0, 10, 10, 10], "points": points, "srs": {"authority": "EPSG:32610"}}), encoding="utf-8")


class Phase27JEptTests(unittest.TestCase):
    def _request(self, root: Path) -> PolygonBatchRequest:
        polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:32610")
        settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
        return PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings)

    def test_selected_ept_data_resolves_to_parent_ept_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            data = root / "ept-data"
            data.mkdir()
            selection = resolve_ept_selection(data)
            status = select_lidar_repository_path(data)

        self.assertIsNotNone(selection)
        self.assertEqual(selection.ept_json, root / "ept.json")
        self.assertEqual(status.normalized_path, root)
        self.assertIn("EPT data folder detected", status.message)

    def test_ept_data_traversal_is_pruned_and_nodes_are_not_cataloged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            node = root / "ept-data" / "0-0-0-0.laz"
            node.parent.mkdir(parents=True)
            node.write_bytes(b"LASF" + (b"\0" * 371))
            paths = tuple(iter_lidar_paths(root))
            result = build_lidar_catalog(root)
            summary = catalog_summary(result.catalog_path, root)

        self.assertEqual(paths, (root / "ept.json",))
        self.assertEqual(result.discovered_count, 1)
        self.assertEqual(summary.indexed_count, 1)

    def test_preflight_for_ept_shows_one_logical_input_and_no_node_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            node = root / "ept-data" / "0-0-0-0.laz"
            node.parent.mkdir(parents=True)
            node.write_bytes(b"LASF" + (b"\0" * 371))
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))
            text = polygon_preflight_text(report)

        self.assertTrue(report.ready)
        self.assertEqual(len(report.selected_sources), 1)
        self.assertIn("Logical inputs: 1", text)
        self.assertIn("Repository: EPT dataset", text)
        self.assertNotIn("0-0-0-0.laz", text)

    def test_incorrect_node_catalog_detect_and_repair_without_traversing_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            catalog = default_lidar_catalog_path(root)
            root_id = stable_root_id(root)
            rows = []
            for index in range(120):
                relative = f"ept-data/{index}-0-0-0.laz"
                rows.append(LidarCatalogRecord(source_id_for(root_id, relative), root / relative, relative, "laz", 0, 1, 0, 1, point_count=10, root_id=root_id))
            conn = connect_catalog(catalog)
            try:
                upsert_records(conn, rows)
                conn.commit()
            finally:
                conn.close()
            self.assertTrue(incorrect_ept_catalog_detected(catalog, root))
            repair = repair_ept_catalog(catalog, root)
            summary = catalog_summary(catalog, root)
            backup_exists = repair.backup_path.exists() if repair.backup_path is not None else False

        self.assertTrue(repair.repaired)
        self.assertEqual(repair.removed_internal_records, 120)
        self.assertEqual(summary.indexed_count, 1)
        self.assertIsNotNone(repair.backup_path)
        self.assertTrue(backup_exists)

    def test_preflight_blocks_when_pbm_import_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (False, "Required dependency is not importable: pyforestscan.handlers"))
            text = polygon_preflight_text(report)

        self.assertFalse(report.ready)
        self.assertIn("Managed processing backend cannot import PyForestScan", report.blockers[0])
        self.assertIn("Backend: PBM Not Ready", text)
        self.assertIn("pyforestscan.handlers", text)

    def test_implausible_point_estimate_becomes_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json", points=10**14)
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))
            text = polygon_preflight_text(report)

        self.assertIsNone(report.estimated_point_count)
        self.assertIn("Not available for this repository", text)
        self.assertTrue(any("reliable polygon-subset estimate" in warning for warning in report.warnings))

    def test_query_timing_components_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "ept-full"
            write_ept(root / "ept.json")
            build_lidar_catalog(root)
            report = run_polygon_batch_preflight(self._request(root), backend_probe=lambda: (True, "PBM backend is ready."))
            timing = report.query_result.timing_seconds if report.query_result else {}

        self.assertIn("rtree_lookup", timing)
        self.assertIn("row_loading", timing)
        self.assertIn("workload_estimation", timing)
        self.assertIn("total_preflight_query", timing)

    def test_move_catalog_to_local_storage_copies_legacy_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "remote" / "lidar"
            root.mkdir(parents=True)
            legacy = repository_side_lidar_catalog_path(root)
            legacy.parent.mkdir(parents=True)
            legacy.write_text("catalog", encoding="utf-8")
            old_localappdata = __import__("os").environ.get("LOCALAPPDATA")
            __import__("os").environ["LOCALAPPDATA"] = str(Path(tmpdir) / "local-app-data")
            try:
                report = move_lidar_catalog_to_local_storage(root, legacy)
                moved = report.moved
                source_exists = report.source_path.exists()
                destination_exists = report.destination_path.exists()
                destination_text = str(report.destination_path)
            finally:
                if old_localappdata is None:
                    __import__("os").environ.pop("LOCALAPPDATA", None)
                else:
                    __import__("os").environ["LOCALAPPDATA"] = old_localappdata

        self.assertTrue(moved)
        self.assertTrue(source_exists)
        self.assertTrue(destination_exists)
        self.assertIn("PyForestScan", destination_text)

    def test_mounted_repository_defaults_to_local_catalog_storage(self) -> None:
        root = Path("/mnt/x/projects/lidar/ept-full")
        catalog = default_lidar_catalog_path(root)
        legacy = repository_side_lidar_catalog_path(root)

        self.assertNotEqual(catalog, legacy)
        self.assertIn("PyForestScan", str(catalog))
        self.assertTrue(str(catalog).endswith("catalog.sqlite"))


if __name__ == "__main__":
    unittest.main()
