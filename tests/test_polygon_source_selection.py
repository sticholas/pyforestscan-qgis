"""QGIS-free coverage for Phase 27E polygon source selection."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyforestscan_qgis.core.polygon_normalization import normalize_polygon_source, normalized_selection_from_wkt
from pyforestscan_qgis.core.polygon_source import (
    POLYGON_VECTOR_FILE_FILTER,
    PolygonSource,
    is_supported_polygon_vector_extension,
    polygon_source_summary,
    selected_feature_count_text,
    stale_layer_message,
    validate_polygon_source,
)
from pyforestscan_qgis.core.spatial_selection import polygon_selection_from_wkt

ROOT = Path(__file__).resolve().parents[1]


class PolygonSourceModelTests(unittest.TestCase):
    """Polygon source models stay QGIS-free and explicit."""

    def test_supported_vector_extensions_include_guided_formats(self) -> None:
        for suffix in (".gpkg", ".shp", ".geojson", ".json", ".fgb", ".kml"):
            self.assertTrue(is_supported_polygon_vector_extension(f"boundary{suffix}"))
        self.assertFalse(is_supported_polygon_vector_extension("boundary.txt"))
        self.assertIn("*.gpkg", POLYGON_VECTOR_FILE_FILTER)
        self.assertIn("*.fgb", POLYGON_VECTOR_FILE_FILTER)

    def test_source_mode_validation_rejects_empty_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "Select one or more"):
            validate_polygon_source(PolygonSource(source_mode="qgis_selected_features", layer_id="layer-1"))

    def test_source_mode_validation_rejects_unsupported_vector_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported polygon vector"):
            validate_polygon_source(PolygonSource(source_mode="vector_file", vector_file_path=Path("poly.txt")))

    def test_wkt_fallback_normalizes_to_selection(self) -> None:
        normalized = normalize_polygon_source(
            PolygonSource(
                source_mode="wkt",
                polygon_wkt="POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
                source_crs="EPSG:4326",
            )
        )
        self.assertEqual(normalized.geometry_type, "Polygon")
        self.assertEqual(normalized.bounds.xmax, 2.0)
        self.assertIn("Advanced WKT", normalized.source_description)
        self.assertTrue(any("WKT is an Advanced fallback" in warning for warning in normalized.warnings))

    def test_multipolygon_wkt_supported_and_point_rejected(self) -> None:
        selection = normalized_selection_from_wkt("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)))", "EPSG:4326")
        self.assertEqual(selection.geometry_type, "MultiPolygon")
        with self.assertRaisesRegex(ValueError, "POLYGON or MULTIPOLYGON"):
            polygon_selection_from_wkt("POINT (0 0)", "EPSG:4326")

    def test_polygon_source_summary_keeps_status_words(self) -> None:
        normalized = normalized_selection_from_wkt("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))", "EPSG:32610")
        summary = polygon_source_summary(normalized)
        self.assertIn("Polygon source:", summary)
        self.assertIn("Geometry: Polygon", summary)
        self.assertIn("CRS: EPSG:32610", summary)

    def test_selected_count_and_stale_layer_text(self) -> None:
        self.assertEqual(selected_feature_count_text(1), "1 selected feature")
        self.assertEqual(selected_feature_count_text(3), "3 selected features")
        self.assertIn("Refresh Layers", stale_layer_message("plots"))


class PolygonSourceUiStaticTests(unittest.TestCase):
    """Static checks for QGIS-facing UI integration."""

    def test_batch_page_exposes_guided_polygon_sources(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn("Use QGIS Layer", source)
        self.assertIn("Choose Vector File", source)
        self.assertIn("Advanced WKT", source)
        self.assertIn("Refresh Polygon Layers", source)
        self.assertIn("Use Selected Features", source)
        self.assertIn("Use Entire Layer", source)
        self.assertIn("run_polygon_batch_preflight", source)

    def test_guided_mode_no_longer_requires_wkt(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertIn("Polygon Selection", source)
        self.assertNotIn("selected QGIS feature support is planned", source)

    def test_qgis_helper_filters_polygon_layers_and_vector_containers(self) -> None:
        source = (ROOT / "pyforestscan_qgis/ui/polygon_source_selector.py").read_text(encoding="utf-8")
        self.assertIn("querySublayers", source)
        self.assertIn("QgsVectorLayer", source)
        self.assertIn("PolygonGeometry", source)
        self.assertIn("unaryUnion", source)
        self.assertIn("makeValid", source)

    def test_ept_subset_accepts_polygon_feature_source(self) -> None:
        source = (ROOT / "pyforestscan_qgis/algorithms/advanced/ept_subset.py").read_text(encoding="utf-8")
        self.assertIn("QgsProcessingParameterFeatureSource", source)
        self.assertIn("TypeVectorPolygon", source)
        self.assertIn("Choose either Polygon feature source or Advanced poly", source)
        self.assertIn("_feature_source_to_wkt", source)


if __name__ == "__main__":
    unittest.main()
