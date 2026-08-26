"""Phase 31D folder/polygon spatial-contract regressions."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.direct_lidar_selection import DirectLidarFolderSelector
from pyforestscan_qgis.core.effective_source_spatial_profile import resolve_effective_source_spatial_profile
from pyforestscan_qgis.core.lidar_source_metadata import HeaderMetadataService, LidarSourceMetadata
from pyforestscan_qgis.core.lidar_catalog_builder import build_lidar_catalog
from pyforestscan_qgis.core.polygon_batch import PolygonBatchRequest, run_polygon_batch_preflight
from pyforestscan_qgis.core.polygon_normalization import normalized_selection_from_wkt
from pyforestscan_qgis.core.processing_spatial_context import PolygonAlignmentFallbackChoice, SourceLocalFallbackPolicy
from pyforestscan_qgis.core.spatial_reference_resolver import SpatialReferenceAssignmentStore, SpatialReferenceStatus
from pyforestscan_qgis.core.spatial_selection import Bounds2D
from pyforestscan_qgis.core.types import ProductType


def _write_las(path: Path, bounds: tuple[float, float, float, float]) -> None:
    header = bytearray(375)
    header[:4] = b"LASF"
    struct.pack_into("<I", header, 107, 104_819_538)
    struct.pack_into("<ddd", header, 131, 0.01, 0.01, 0.01)
    struct.pack_into("<ddd", header, 155, 0.0, 0.0, 0.0)
    xmin, xmax, ymin, ymax = bounds
    struct.pack_into("<dddddd", header, 179, xmax, xmin, ymax, ymin, 100.0, 0.0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)


class EffectiveSpatialProfileTests(unittest.TestCase):
    def test_live_shape_unknown_member_inherits_repository_assignment_before_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            source = root / "nested" / "Olaa_sanitized.las"
            _write_las(source, (271368.874, 272118.751, 2152762.757, 2153464.879))
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_repository(root, "EPSG:6635")
            polygon = normalized_selection_from_wkt(
                "POLYGON ((271371 2152760, 272114 2152760, 272114 2153460, 271371 2153460, 271371 2152760))",
                "EPSG:6635",
            )
            result = DirectLidarFolderSelector(assignment_store=store).select(root, polygon)

        self.assertTrue(result.ready)
        self.assertEqual(1, result.intersecting_source_count)
        self.assertEqual("EPSG:6635", result.selected_sources[0].crs)
        self.assertNotIn("coordinate system is unknown", " ".join(result.blockers).lower())

    def test_polygon_still_blocks_without_real_crs(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _write_las(root / "unknown.las", (0, 10, 0, 10))
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 9 1, 9 9, 1 9, 1 1))", "EPSG:6635")
            store = SpatialReferenceAssignmentStore(root / "empty.json")
            strict = SourceLocalFallbackPolicy(polygon_alignment=PolygonAlignmentFallbackChoice.REQUIRE_EXPLICIT_CRS)
            result = DirectLidarFolderSelector(assignment_store=store, spatial_policy=strict).select(root, polygon)

        self.assertFalse(result.ready)
        self.assertIn("Use Project CRS or Choose CRS", " ".join(result.blockers))

    def test_embedded_crs_conflict_blocks_repository_inheritance(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            source = root / "known.las"
            source.write_bytes(b"LAS")
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_repository(root, "EPSG:6635")
            metadata = LidarSourceMetadata(source, source, "las", True, True, 3, 1, embedded_crs="EPSG:32605", effective_crs="EPSG:32605")
            profile = resolve_effective_source_spatial_profile(metadata, root, assignment_store=store, polygon_crs="EPSG:6635")

        self.assertEqual(SpatialReferenceStatus.CONFLICT, profile.status)
        self.assertFalse(profile.safe_for_spatial_alignment)

    def test_different_crs_uses_transformer_before_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _write_las(root / "tile.las", (100, 110, 100, 110))
            polygon = normalized_selection_from_wkt("POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))", "EPSG:4326")
            result = DirectLidarFolderSelector(
                bounds_transformer=lambda bounds, _source, _target: Bounds2D(bounds.xmin + 100, bounds.ymin + 100, bounds.xmax + 100, bounds.ymax + 100),
                assignment_store=SpatialReferenceAssignmentStore(root / "empty.json"),
            ).select(root, polygon, repository_crs_override="EPSG:6635")

        self.assertTrue(result.ready)
        self.assertEqual(1, result.intersecting_source_count)

    def test_raw_catalog_metadata_remains_unmodified(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            source = root / "tile.las"
            _write_las(source, (0, 10, 0, 10))
            metadata = HeaderMetadataService().discover(root)[0]
            store = SpatialReferenceAssignmentStore(Path(folder) / "assignments.json")
            store.assign_repository(root, "EPSG:6635")
            profile = resolve_effective_source_spatial_profile(metadata, root, assignment_store=store, polygon_crs="EPSG:6635")

        self.assertIsNone(metadata.embedded_crs)
        self.assertIsNone(metadata.effective_crs)
        self.assertEqual("EPSG:6635", profile.effective_crs)

    def test_catalog_and_direct_scan_use_same_effective_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            source = root / "tile.las"
            _write_las(source, (0, 10, 0, 10))
            catalog = build_lidar_catalog(root).catalog_path
            polygon = normalized_selection_from_wkt("POLYGON ((1 1, 9 1, 9 9, 1 9, 1 1))", "EPSG:6635")
            settings = BatchProductSettings(products=(ProductType.CHM,), grid_resolution=1.0)
            request = PolygonBatchRequest(root, Path(folder) / "out", polygon, (ProductType.CHM,), settings, catalog_path=catalog, direct_header_fallback=False)
            with patch("pyforestscan_qgis.core.polygon_batch.shared_repository_crs", return_value=("EPSG:6635", "USER_REPOSITORY_ASSIGNMENT")):
                catalog_report = run_polygon_batch_preflight(request, backend_probe=lambda: (True, "PBM ready"))
            direct = DirectLidarFolderSelector(assignment_store=SpatialReferenceAssignmentStore(Path(folder) / "empty.json")).select(root, polygon, repository_crs_override="EPSG:6635")

        self.assertEqual("catalog", catalog_report.selection_method)
        self.assertEqual(direct.intersecting_source_paths, tuple(item.path for item in catalog_report.selected_sources))
        self.assertEqual("EPSG:6635", catalog_report.selected_sources[0].crs)


if __name__ == "__main__":
    unittest.main()
