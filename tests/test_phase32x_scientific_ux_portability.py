"""Phase 32X scientific UX, fallback CRS, and portability contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pyforestscan_qgis.compat.qt import install_enum_aliases, qt_enum
from pyforestscan_qgis.core.platform_compat import conda_platform_subdir, normalize_architecture
from pyforestscan_qgis.core.owned_workers import terminate_process_tree
from pyforestscan_qgis.core.processing_spatial_context import (
    EffectiveSpatialMode,
    PolygonAlignmentFallbackChoice,
    SourceLocalFallbackPolicy,
    SourceLocalFallbackPolicyStore,
    policy_with_fallback_crs,
    resolve_effective_spatial_context,
)
from pyforestscan_qgis.core.spatial_selection import Bounds2D
from pyforestscan_qgis.ui.help_topics import SEMANTIC_CONTEXT_HELP


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class ScientificLayoutAndHelpTests(unittest.TestCase):
    def test_advanced_body_uses_current_layout_hint_not_unbounded_height(self) -> None:
        self.assertIn("_fit_collapsible_to_visible_content", PAGES)
        self.assertIn("layout.sizeHint().height()", PAGES)
        self.assertNotIn("content.setMaximumHeight(16777215 if visible else 0)", PAGES)
        self.assertNotIn("advanced_product_settings_group.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)", PAGES)
        self.assertIn('getattr(form, "setRowVisible", None)', PAGES)
        self.assertIn("def _rebuild_product_settings_form", PAGES)
        self.assertIn("form.takeAt(0)", PAGES)

    def test_official_calculation_reference_is_compact_and_exact(self) -> None:
        self.assertIn("https://pyforestscan.sefa.ai/api/calculate/", PAGES)
        self.assertIn('QPushButton("Calculation Reference")', PAGES)
        self.assertIn("QSizePolicy.Fixed, QSizePolicy.Fixed", PAGES)

    def test_semantic_registry_covers_products_and_scientific_parameters(self) -> None:
        required = {
            "process.folder.discover", "process.folder.clear", "process.polygon.layer",
            "product.chm", "product.pad", "product.pai", "product.fhd", "product.rumple",
            "product.canopy_cover", "product.point_density", "product.voxel_stat", "product.dtm",
            "parameter.grid_resolution", "parameter.chm.interpolation", "parameter.fhd.min_height",
            "parameter.pad.beer_lambert", "tools.fallback_crs",
        }
        self.assertTrue(required.issubset(SEMANTIC_CONTEXT_HELP))

    def test_generic_generated_help_is_removed(self) -> None:
        banned = (
            "for the current workflow", "continue this page action",
            "Set {label or 'this value'}", "Choose {label}",
        )
        for phrase in banned:
            self.assertNotIn(phrase, PAGES)


class FallbackCrsTests(unittest.TestCase):
    def test_policy_round_trip_records_explicit_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = SourceLocalFallbackPolicyStore(Path(folder) / "policy.json")
            store.write(policy_with_fallback_crs(SourceLocalFallbackPolicy(), "EPSG:6635"))
            restored = store.read()
        self.assertEqual("EPSG:6635", restored.fallback_crs)
        self.assertTrue(restored.fallback_crs_configured_at)

    def test_authoritative_crs_always_wins(self) -> None:
        policy = policy_with_fallback_crs(SourceLocalFallbackPolicy(), "EPSG:4326")
        result = resolve_effective_spatial_context(raw_crs="EPSG:6635", policy=policy)
        self.assertEqual("EPSG:6635", result.effective_crs)
        self.assertFalse(result.fallback_used)

    def test_safe_fallback_is_explicit_and_does_not_transform(self) -> None:
        policy = policy_with_fallback_crs(
            SourceLocalFallbackPolicy(polygon_alignment=PolygonAlignmentFallbackChoice.ASK), "EPSG:6635"
        )
        bounds = Bounds2D(100, 100, 200, 200)
        result = resolve_effective_spatial_context(
            polygon_crs="EPSG:6635", source_bounds=bounds, polygon_bounds=bounds,
            polygon_alignment_required=True, policy=policy,
        )
        self.assertEqual(EffectiveSpatialMode.USER_FALLBACK_CRS, result.mode)
        self.assertEqual("CRS ASSUMED FROM USER FALLBACK", result.provenance)
        self.assertFalse(result.coordinates_transformed)
        self.assertIn("Fallback CRS preference", result.warnings[0])
        self.assertTrue(result.fallback_crs_configured_at)
        self.assertIn("no usable CRS metadata", result.fallback_reason)
        self.assertTrue(result.compatibility.strong)

    def test_unsafe_fallback_does_not_force_mismatched_coordinates(self) -> None:
        policy = policy_with_fallback_crs(
            SourceLocalFallbackPolicy(polygon_alignment=PolygonAlignmentFallbackChoice.ASK), "EPSG:4326"
        )
        result = resolve_effective_spatial_context(
            polygon_crs="EPSG:4326", source_bounds=Bounds2D(200000, 2100000, 201000, 2101000),
            polygon_bounds=Bounds2D(-156, 19, -155, 20), polygon_alignment_required=True, policy=policy,
        )
        self.assertEqual(EffectiveSpatialMode.UNRESOLVED, result.mode)
        self.assertTrue(result.blockers)


class PlatformPolicyTests(unittest.TestCase):
    def test_supported_conda_architecture_mapping_is_explicit(self) -> None:
        self.assertEqual("win-64", conda_platform_subdir("Windows", "AMD64"))
        self.assertEqual("win-arm64", conda_platform_subdir("Windows", "ARM64"))
        self.assertEqual("osx-64", conda_platform_subdir("Darwin", "x86_64"))
        self.assertEqual("osx-arm64", conda_platform_subdir("Darwin", "arm64"))
        self.assertEqual("linux-64", conda_platform_subdir("Linux", "x86_64"))
        self.assertEqual("linux-aarch64", conda_platform_subdir("Linux", "aarch64"))
        self.assertEqual("arm64", normalize_architecture("aarch64"))

    def test_unknown_host_is_not_mapped_optimistically(self) -> None:
        self.assertEqual("", conda_platform_subdir("FreeBSD", "amd64"))

    def test_qt_enum_supports_qt5_and_qt6_shapes(self) -> None:
        qt5 = type("Qt5", (), {"AllDockWidgetAreas": 15})
        qt6 = type("Qt6", (), {"DockWidgetArea": type("Scope", (), {"AllDockWidgetAreas": 31})})
        self.assertEqual(15, qt_enum(qt5, "AllDockWidgetAreas", "DockWidgetArea"))
        self.assertEqual(31, qt_enum(qt6, "AllDockWidgetAreas", "DockWidgetArea"))
        install_enum_aliases(qt6, "DockWidgetArea", ("AllDockWidgetAreas",))
        self.assertEqual(31, qt6.AllDockWidgetAreas)

        frame = type("Frame", (), {"Shape": type("Shape", (), {"StyledPanel": 6})})
        install_enum_aliases(frame, "Shape", ("StyledPanel",))
        self.assertEqual(6, frame.StyledPanel)

    @patch("pyforestscan_qgis.core.owned_workers.subprocess.run")
    def test_windows_worker_termination_is_owned_tree_only(self, run: Mock) -> None:
        process = Mock(pid=4321)
        process.poll.return_value = None
        terminate_process_tree(process, os_name="nt")
        command = run.call_args.args[0]
        self.assertEqual(["taskkill", "/PID", "4321", "/T", "/F"], command)
        process.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
