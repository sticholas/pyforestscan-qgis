"""Phase 31E unified spatial fallback and overlap-truth regressions."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.direct_lidar_selection import DirectLidarFolderSelector
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight, write_polygon_batch_manifest
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.processing_spatial_context import (
    EffectiveSpatialMode,
    PolygonAlignmentFallbackChoice,
    SourceLocalFallbackChoice,
    SourceLocalFallbackPolicy,
    SourceLocalFallbackPolicyStore,
    evaluate_coordinate_space_compatibility,
)
from pyforestscan_qgis.core.spatial_assignment import LinearUnit
from pyforestscan_qgis.core.spatial_reference_resolver import SpatialReferenceAssignmentStore
from pyforestscan_qgis.core.spatial_selection import Bounds2D
from pyforestscan_qgis.core.types import ProductType


SOURCE_BOUNDS = Bounds2D(271368.874, 2152762.757, 272118.751, 2153464.879)
POLYGON_BOUNDS = Bounds2D(271371.0, 2152760.0, 272114.0, 2153460.0)


def _write_las(path: Path, bounds: Bounds2D) -> None:
    header = bytearray(375)
    header[:4] = b"LASF"
    struct.pack_into("<I", header, 107, 104_819_538)
    struct.pack_into("<ddd", header, 131, 0.01, 0.01, 0.01)
    struct.pack_into("<ddd", header, 155, 0.0, 0.0, 0.0)
    struct.pack_into("<dddddd", header, 179, bounds.xmax, bounds.xmin, bounds.ymax, bounds.ymin, 100.0, 0.0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)


def _polygon(bounds: Bounds2D, crs: str = "EPSG:6635"):
    return normalized_selection_from_wkt(
        f"POLYGON (({bounds.xmin} {bounds.ymin}, {bounds.xmax} {bounds.ymin}, {bounds.xmax} {bounds.ymax}, {bounds.xmin} {bounds.ymax}, {bounds.xmin} {bounds.ymin}))",
        crs,
    )


class CoordinateCompatibilityTests(unittest.TestCase):
    def test_exact_current_bounds_are_strong_raw_overlap(self) -> None:
        result = evaluate_coordinate_space_compatibility(SOURCE_BOUNDS, POLYGON_BOUNDS)
        self.assertGreater(result.x_overlap, 0)
        self.assertGreater(result.y_overlap, 0)
        self.assertTrue(result.raw_overlap)
        self.assertTrue(result.strong)

    def test_projected_lidar_and_geographic_polygon_are_incompatible(self) -> None:
        geographic = Bounds2D(-155.5, 19.0, -155.0, 19.5)
        result = evaluate_coordinate_space_compatibility(SOURCE_BOUNDS, geographic)
        self.assertFalse(result.raw_overlap)
        self.assertFalse(result.strong)


class PolygonFallbackTests(unittest.TestCase):
    def test_unknown_current_source_uses_assumed_polygon_coordinate_space(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            source = root / "Olaa.las"
            _write_las(source, SOURCE_BOUNDS)
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            result = DirectLidarFolderSelector(assignment_store=store).select(root, _polygon(POLYGON_BOUNDS))

        self.assertTrue(result.ready)
        self.assertEqual((source,), result.intersecting_source_paths)
        self.assertEqual("EPSG:6635", result.selected_sources[0].crs)
        context = result.spatial_contexts[0]
        self.assertEqual(EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE, context.mode)
        self.assertEqual(LinearUnit.METERS, context.units)
        self.assertFalse(context.coordinates_transformed)
        self.assertTrue(context.fallback_used)

    def test_strict_policy_reports_raw_overlap_without_claiming_geometric_no(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            _write_las(root / "Olaa.las", SOURCE_BOUNDS)
            strict = SourceLocalFallbackPolicy(polygon_alignment=PolygonAlignmentFallbackChoice.REQUIRE_EXPLICIT_CRS)
            result = DirectLidarFolderSelector(assignment_store=SpatialReferenceAssignmentStore(Path(folder) / "none.json"), spatial_policy=strict).select(root, _polygon(POLYGON_BOUNDS))

        self.assertFalse(result.ready)
        self.assertTrue(result.rejected_sources[0].raw_overlap)
        self.assertEqual("blocked", result.rejected_sources[0].spatial_alignment)
        self.assertNotIn("no LiDAR tiles overlap", " ".join(result.blockers))

    def test_incompatible_unknown_source_does_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            _write_las(root / "Olaa.las", SOURCE_BOUNDS)
            geographic = Bounds2D(-155.5, 19.0, -155.0, 19.5)
            result = DirectLidarFolderSelector(assignment_store=SpatialReferenceAssignmentStore(Path(folder) / "none.json")).select(root, _polygon(geographic, "EPSG:4326"))

        self.assertFalse(result.ready)
        self.assertFalse(result.rejected_sources[0].raw_overlap)
        self.assertEqual("CRS_MISSING", result.rejected_sources[0].reason_code)


class PolicyAndAssignmentTests(unittest.TestCase):
    def test_polygon_policy_round_trips_without_changing_folder_units(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = SourceLocalFallbackPolicyStore(Path(folder) / "policy.json")
            policy = SourceLocalFallbackPolicy(SourceLocalFallbackChoice.US_SURVEY_FEET, 1, PolygonAlignmentFallbackChoice.ASK)
            store.write(policy)
            restored = store.read()
        self.assertEqual(SourceLocalFallbackChoice.US_SURVEY_FEET, restored.default_units)
        self.assertEqual(PolygonAlignmentFallbackChoice.ASK, restored.polygon_alignment)

    def test_repository_assignment_applies_to_descendant_and_survives_catalog_churn(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            source = root / "nested" / "tile.las"
            _write_las(source, SOURCE_BOUNDS)
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_repository(root, "EPSG:6635")
            (root / "lidar_catalog.sqlite").write_text("cache changed", encoding="utf-8")
            assignment = store.spatial_assignment_for(source, root)
            diagnostic = store.assignment_diagnostics(source, root)

        self.assertIsNotNone(assignment)
        self.assertEqual("EPSG:6635", assignment.horizontal_crs)
        self.assertTrue(diagnostic["assignment_fingerprint_match"])
        self.assertTrue(diagnostic["assignment_effective"])


class SpatialTraceTests(unittest.TestCase):
    def test_preflight_writes_effective_trace_and_assumed_output_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            _write_las(root / "Olaa.las", SOURCE_BOUNDS)
            settings = BatchProductSettings(products=(ProductType.CHM, ProductType.RUMPLE), grid_resolution=1.0)
            request = PolygonBatchRequest(root, Path(folder) / "out", _polygon(POLYGON_BOUNDS), (ProductType.CHM, ProductType.RUMPLE), settings, selection_mode="direct_header_scan")
            report = run_polygon_batch_preflight(request, backend_probe=lambda: (True, "PBM ready"))
            manifest_path = write_polygon_batch_manifest(report)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            trace = json.loads((report.batch_folder / "effective_spatial_trace.json").read_text(encoding="utf-8"))

        self.assertTrue(report.ready)
        self.assertEqual("ASSUMED_MATCHING_COORDINATE_SPACE", trace["sources"][0]["spatial_mode"])
        self.assertTrue(trace["sources"][0]["raw_coordinate_overlap"])
        self.assertEqual("assumed", trace["sources"][0]["spatial_alignment"])
        self.assertTrue(trace["sources"][0]["final_source_selected"])
        self.assertIn("assignment_store_path", trace["sources"][0])
        self.assertEqual("assumed_matching_coordinate_space", manifest["spatial_provenance"]["SOURCE_CRS_BASIS"])
        self.assertFalse(manifest["spatial_provenance"]["COORDINATES_TRANSFORMED"])
        self.assertTrue(manifest["spatial_provenance"]["SPATIAL_FALLBACK_USED"])

    def test_polygon_request_freezes_strict_policy_into_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            _write_las(root / "Olaa.las", SOURCE_BOUNDS)
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            strict = SourceLocalFallbackPolicy(polygon_alignment=PolygonAlignmentFallbackChoice.REQUIRE_EXPLICIT_CRS)
            request = PolygonBatchRequest(root, Path(folder) / "out", _polygon(POLYGON_BOUNDS), (ProductType.CHM,), settings, selection_mode="direct_header_scan", spatial_policy=strict)
            report = run_polygon_batch_preflight(request, backend_probe=lambda: (True, "PBM ready"))

        self.assertFalse(report.ready)
        self.assertEqual(strict, report.request.spatial_policy)
        self.assertEqual("Blocked", report.spatial_alignment_status)

    def test_ui_refreshes_polygon_preflight_when_policy_changes(self) -> None:
        source = (Path(__file__).parents[1] / "pyforestscan_qgis" / "ui" / "pages.py").read_text(encoding="utf-8")
        self.assertIn('if getattr(getattr(report, "request", None), "spatial_policy", None) != current_policy:', source)
        self.assertIn("build_current_processing_request", source)


if __name__ == "__main__":
    unittest.main()
