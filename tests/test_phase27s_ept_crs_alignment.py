"""Phase 27S EPT CRS resolution and spatial-alignment regressions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.backend_runner.request_validation import _ept_crs
from pyforestscan_qgis.core.adapter import _crs_from_ept_metadata
from pyforestscan_qgis.core.crs_alignment import align_polygon_to_crs
from pyforestscan_qgis.core.ept_spatial_reference import INCOMPLETE_CRS_AUTHORITY, is_incomplete_crs_identifier, resolve_ept_spatial_reference
from pyforestscan_qgis.core.lidar_catalog import connect_catalog, upsert_records
from pyforestscan_qgis.core.lidar_catalog_builder import inspect_lidar_header
from pyforestscan_qgis.core.lidar_catalog_models import stable_root_id
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.polygon_source_selection import PolygonSourceSelectionService


def _ept(root: Path, srs: dict[str, object], bounds=(0, 0, 0, 10, 10, 5)) -> Path:
    path = root / "ept.json"
    path.write_text(json.dumps({"bounds": list(bounds), "points": 100, "srs": srs}), encoding="utf-8")
    return path


class EptCrsResolutionTests(unittest.TestCase):
    def test_authority_horizontal_integer_resolves_complete_authid(self) -> None:
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "EPSG", "horizontal": 6635}})
        self.assertTrue(resolved.valid)
        self.assertEqual(resolved.authid, "EPSG:6635")
        self.assertEqual(resolved.authority, "EPSG")
        self.assertEqual(resolved.horizontal_code, "6635")
        self.assertEqual(resolved.source, "ept_authority_code")

    def test_authority_horizontal_string_resolves_complete_authid(self) -> None:
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "epsg", "horizontal": "32610"}})
        self.assertEqual(resolved.crs_text, "EPSG:32610")

    def test_vertical_code_is_recorded_separately(self) -> None:
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "EPSG", "horizontal": "6635", "vertical": "5703"}})
        self.assertEqual(resolved.authid, "EPSG:6635")
        self.assertEqual(resolved.vertical_code, "5703")

    def test_complete_authority_authid_remains_supported(self) -> None:
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "EPSG:32610"}})
        self.assertTrue(resolved.valid)
        self.assertEqual(resolved.authid, "EPSG:32610")

    def test_authority_takes_priority_and_retains_wkt(self) -> None:
        wkt = 'PROJCS["Fake projected CRS",UNIT["metre",1]]'
        resolved = resolve_ept_spatial_reference({"srs": {"wkt2": wkt, "authority": "EPSG", "horizontal": "6635"}})
        self.assertTrue(resolved.valid)
        self.assertEqual(resolved.source, "ept_authority_code")
        self.assertEqual(resolved.authid, "EPSG:6635")
        self.assertEqual(resolved.wkt, wkt)

    def test_authority_takes_priority_and_retains_projjson(self) -> None:
        projjson = {"type": "ProjectedCRS", "name": "Fake projected CRS"}
        resolved = resolve_ept_spatial_reference({"srs": {"projjson": projjson, "authority": "EPSG", "horizontal": "6635"}})
        self.assertTrue(resolved.valid)
        self.assertEqual(resolved.source, "ept_authority_code")
        self.assertEqual(resolved.projjson, projjson)

    def test_incomplete_authority_is_rejected(self) -> None:
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "EPSG"}})
        self.assertFalse(resolved.valid)
        self.assertIn(INCOMPLETE_CRS_AUTHORITY, resolved.errors)
        self.assertTrue(is_incomplete_crs_identifier("EPSG"))
        self.assertTrue(is_incomplete_crs_identifier("EPSG:"))
        self.assertTrue(is_incomplete_crs_identifier(":6635"))

    def test_horizontal_only_and_malformed_code_are_rejected(self) -> None:
        self.assertFalse(resolve_ept_spatial_reference({"srs": {"horizontal": "6635"}}).valid)
        self.assertFalse(resolve_ept_spatial_reference({"srs": {"authority": "EPSG", "horizontal": "abc"}}).valid)

    def test_empty_and_missing_srs_are_rejected(self) -> None:
        self.assertFalse(resolve_ept_spatial_reference({"srs": {}}).valid)
        self.assertFalse(resolve_ept_spatial_reference({}).valid)

    def test_catalog_backend_and_adapter_use_complete_authid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _ept(root, {"authority": "EPSG", "horizontal": 6635})
            record = inspect_lidar_header(path, root, stable_root_id(root))
            self.assertEqual(record.source_crs, "EPSG:6635")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(_ept_crs(payload), "EPSG:6635")
            self.assertEqual(_crs_from_ept_metadata(payload), "EPSG:6635")
            self.assertEqual(_crs_from_ept_metadata({"srs": {"authority": "EPSG:32610"}}), "EPSG:32610")


class EptSpatialAlignmentTests(unittest.TestCase):
    def test_same_crs_fast_path_uses_original_geometry(self) -> None:
        polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:6635")
        aligned = align_polygon_to_crs(polygon, "EPSG:6635")
        self.assertTrue(aligned.ready)
        self.assertFalse(aligned.transformation_required)
        self.assertEqual(aligned.transformed_wkt, polygon.geometry_wkt)
        self.assertEqual(aligned.transformed_bounds.xmin, 1)

    def test_different_crs_uses_injected_exact_geometry_transform(self) -> None:
        polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:4326")

        def factory(_source: str, _target: str):
            def transform(x: float, y: float) -> tuple[float, float]:
                return x + 1000, y + 2000
            return transform

        aligned = align_polygon_to_crs(polygon, "EPSG:6635", transformer_factory=factory)
        self.assertTrue(aligned.ready)
        self.assertTrue(aligned.transformation_required)
        self.assertEqual(aligned.transformed_bounds.xmin, 1001)
        self.assertEqual(aligned.transformed_bounds.ymax, 2004)

    def test_transform_failure_is_not_no_coverage(self) -> None:
        polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:4326")

        def factory(_source: str, _target: str):
            raise ValueError("not available")

        aligned = align_polygon_to_crs(polygon, "EPSG:6635", transformer_factory=factory)
        self.assertFalse(aligned.ready)
        self.assertEqual(aligned.status, "transformation_unavailable")
        self.assertIn("CRS_TRANSFORM_FAILED", aligned.errors)

    def test_incomplete_saved_ept_catalog_crs_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _ept(root, {"authority": "EPSG", "horizontal": 6635}, bounds=(0, 0, 0, 10, 10, 5))
            catalog = root / ".pyforestscan" / "lidar_catalog.sqlite"
            catalog.parent.mkdir(parents=True, exist_ok=True)
            record = inspect_lidar_header(path, root, stable_root_id(root))
            connection = connect_catalog(catalog)
            try:
                upsert_records(connection, (record,))
                connection.execute("UPDATE lidar_sources SET source_crs = 'EPSG' WHERE relative_path = 'ept.json'")
                connection.commit()
            finally:
                connection.close()
            service = PolygonSourceSelectionService()
            repository = service.resolve_repository(root, catalog)
            self.assertEqual(repository.source_crs, "EPSG:6635")
            self.assertIn("EPT coordinate-system metadata was repaired.", repository.warnings)
            connection = connect_catalog(catalog)
            try:
                row = connection.execute("SELECT source_crs FROM lidar_sources WHERE relative_path = 'ept.json'").fetchone()
            finally:
                connection.close()
            self.assertEqual(row["source_crs"], "EPSG:6635")

    def test_exact_epsg6635_regression_selects_one_logical_ept_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _ept(root, {"authority": "EPSG", "horizontal": 6635}, bounds=(167757, 2092940, 0, 318703, 2243880, 100))
            polygon = normalized_selection_from_wkt(
                "POLYGON ((197779 2235470, 199103 2235470, 199103 2236500, 197779 2236500, 197779 2235470))",
                "EPSG:6635",
            )
            service = PolygonSourceSelectionService()
            repository = service.resolve_repository(root)
            selection = service.select_sources(repository, polygon)
            self.assertEqual(repository.source_crs, "EPSG:6635")
            self.assertEqual(repository.crs_resolution_source, "ept_authority_code")
            self.assertEqual(selection.overlap_result, "yes")
            self.assertEqual(len(selection.selected_sources), 1)
            self.assertFalse(selection.blockers)
            self.assertEqual(selection.spatial_alignment.status, "ready")
            self.assertFalse(selection.spatial_alignment.transformation_required)

    def test_incomplete_ept_crs_does_not_report_no_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _ept(root, {"authority": "EPSG"}, bounds=(0, 0, 0, 10, 10, 5))
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))", "EPSG:6635")
            service = PolygonSourceSelectionService()
            repository = service.resolve_repository(root)
            selection = service.select_sources(repository, polygon)
            texts = " ".join(message.to_text() for message in selection.blockers)
            self.assertIn("coordinate-system metadata is incomplete", texts)
            self.assertNotIn("No LiDAR coverage", texts)
            self.assertEqual(len(selection.selected_sources), 0)

    def test_true_non_overlap_reports_no_coverage_after_crs_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _ept(root, {"authority": "EPSG", "horizontal": 6635}, bounds=(0, 0, 0, 10, 10, 5))
            polygon = normalized_selection_from_wkt("POLYGON ((20 20, 25 20, 25 25, 20 25, 20 20))", "EPSG:6635")
            service = PolygonSourceSelectionService()
            selection = service.select_sources(service.resolve_repository(root), polygon)
            texts = " ".join(message.to_text() for message in selection.blockers)
            self.assertIn("No LiDAR coverage", texts)
            self.assertEqual(selection.overlap_result, "no")


if __name__ == "__main__":
    unittest.main()
