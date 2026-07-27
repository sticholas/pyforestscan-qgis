"""Phase 27P tests for CRS semantics and QGIS spatial action contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.lidar_catalog import connect_catalog
from pyforestscan_qgis.core.lidar_catalog_integrity import (
    assign_repository_crs_override,
    inspect_catalog_integrity,
    inspect_catalog_records,
    remove_repository_crs_override,
)
from pyforestscan_qgis.core.lidar_catalog_models import LidarCatalogRecord, source_id_for, stable_root_id, utc_now_iso
from pyforestscan_qgis.core.lidar_header_verification import verify_header_record
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.repository_coverage import build_repository_coverage_model
from pyforestscan_qgis.core.spatial_selection import Bounds2D
from pyforestscan_qgis.core.types import ProductType
from pyforestscan_qgis.ui.qgis_spatial_actions import add_repository_coverage_to_qgis, combine_bounds, zoom_canvas_to_bounds


def insert_record(root: Path, catalog: Path, relative: str, bounds: tuple[float, float, float, float], *, crs: str | None = None, points: int = 10) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"LASF" + b"0" * 400)
    root_id = stable_root_id(root)
    xmin, xmax, ymin, ymax = bounds
    record = LidarCatalogRecord(
        source_id=source_id_for(root_id, relative),
        source_path=path,
        relative_path=relative,
        source_type="laz",
        xmin=xmin,
        xmax=xmax,
        ymin=ymin,
        ymax=ymax,
        zmin=0,
        zmax=1,
        source_crs=crs,
        point_count=points,
        file_size=path.stat().st_size,
        modified_time_ns=path.stat().st_mtime_ns,
        header_signature="test",
        inventory_status="indexed",
        metadata_error=None,
        indexed_at=utc_now_iso(),
        root_id=root_id,
    )
    from pyforestscan_qgis.core.lidar_catalog import upsert_records
    from pyforestscan_qgis.core.lidar_catalog_integrity import write_catalog_identity

    connection = connect_catalog(catalog)
    try:
        upsert_records(connection, (record,))
        write_catalog_identity(connection, root)
        connection.commit()
    finally:
        connection.close()


class Phase27PLidarCrsTests(unittest.TestCase):
    def test_all_bounded_rows_missing_crs_requires_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            for index in range(214):
                insert_record(root, catalog, f"tile_{index:03d}.laz", (178892 + index, 184000 + index, 2174620, 2192210))
            report = inspect_catalog_integrity(catalog, root)

        self.assertEqual(report.status, "CRS Assignment Required")
        self.assertEqual(report.embedded_crs_known_count, 0)
        self.assertEqual(report.crs_unknown_bounded_count, 214)
        self.assertEqual(report.effective_crs_known_count, 0)
        self.assertIn("CRS_MISSING", report.skip_reason_counts)

    def test_unknown_crs_blocks_no_coverage_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            insert_record(root, catalog, "tile.laz", (178892, 184000, 2174620, 2192210))
            polygon = normalized_selection_from_wkt("POLYGON ((194858 2167140, 195583 2167140, 195583 2169530, 194858 2169530, 194858 2167140))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            preflight = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM ready"))

        self.assertFalse(preflight.ready)
        text = " ".join(preflight.blockers + preflight.warnings)
        self.assertIn("coordinate system is unknown", text)
        self.assertNotIn("Healthy catalog coverage does not overlap", text)
        self.assertFalse(any(item == "No LiDAR coverage was found for this area." for item in preflight.blockers))

    def test_repository_override_enables_effective_crs_and_true_non_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            insert_record(root, catalog, "tile.laz", (178892, 184000, 2174620, 2192210))
            assign_repository_crs_override(catalog, root, "EPSG:6635", assigned_by="test")
            report = inspect_catalog_integrity(catalog, root)
            polygon = normalized_selection_from_wkt("POLYGON ((194858 2167140, 195583 2167140, 195583 2169530, 194858 2169530, 194858 2167140))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            preflight = run_polygon_batch_preflight(PolygonBatchRequest(root, root / "out", polygon, (ProductType.CHM,), settings), backend_probe=lambda: (True, "PBM ready"))
            remove_repository_crs_override(catalog, root)
            restored = inspect_catalog_integrity(catalog, root)

        self.assertEqual(report.status, "Healthy with validated repository CRS override")
        self.assertEqual(report.repository_crs_override, "EPSG:6635")
        self.assertTrue(any("No LiDAR coverage" in item for item in preflight.blockers))
        self.assertEqual(restored.status, "CRS Assignment Required")

    def test_extent_defining_sources_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            insert_record(root, catalog, "minx.laz", (1, 2, 10, 20), crs="EPSG:6635")
            insert_record(root, catalog, "maxx.laz", (5, 9, 11, 21), crs="EPSG:6635")
            inspection = inspect_catalog_records(catalog, root)

        roles = {item.role: item.source_path.name for item in inspection.extent_defining_sources}
        self.assertEqual(roles["minimum_x"], "minx.laz")
        self.assertEqual(roles["maximum_x"], "maxx.laz")

    def test_header_verification_distinguishes_missing_crs(self) -> None:
        root = Path("/tmp")
        stored = LidarCatalogRecord("id", Path("/tmp/tile.laz"), "tile.laz", "laz", xmin=0, xmax=1, ymin=0, ymax=1, point_count=10, root_id="root")
        actual = LidarCatalogRecord("id", Path("/tmp/tile.laz"), "tile.laz", "laz", xmin=0, xmax=1, ymin=0, ymax=1, point_count=10, root_id="root")
        result = verify_header_record(stored, root, reader=lambda *_args: actual)

        self.assertTrue(result.bounds_match)
        self.assertIsNone(result.actual_crs)
        self.assertEqual(result.recommended_action, "Assign Coordinate System")

    def test_coverage_and_zoom_services_fail_without_live_qgis_or_crs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            insert_record(root, catalog, "tile.laz", (0, 1, 0, 1))
            model = build_repository_coverage_model(catalog, root)

        self.assertFalse(add_repository_coverage_to_qgis(model, None).success)
        self.assertFalse(zoom_canvas_to_bounds(Bounds2D(0, 0, 1, 1), None, object(), label="repository").success)
        self.assertEqual(combine_bounds(Bounds2D(0, 0, 1, 1), Bounds2D(2, 2, 3, 3)), Bounds2D(0, 0, 3, 3))

    def test_diagnostic_script_inspect_mode_outputs_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            insert_record(root, catalog, "tile.laz", (0, 1, 0, 1))
            proc = subprocess.run(
                [sys.executable, "scripts/diagnose_real_lidar_repository.py", "--repository", str(root), "--catalog", str(catalog), "--inspect"],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)

        self.assertEqual(payload["catalog"]["status"], "CRS Assignment Required")
        self.assertIn("coordinate system", payload["likely_diagnosis"])


if __name__ == "__main__":
    unittest.main()
