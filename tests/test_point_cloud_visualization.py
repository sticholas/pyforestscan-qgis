import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from pyforestscan_qgis.core.point_cloud.visualization import (
    DisplayRange, LegendModel, RenderState, available_attribute_modes,
    display_range, histogram, nice_tick_step, nice_ticks, numeric_summary,
    resolve_attribute,
)


class PointCloudVisualizationTests(unittest.TestCase):
    def test_attribute_modes_require_source_dimensions(self):
        modes = available_attribute_modes(("X", "Y", "Z", "Classification", "Intensity"))
        self.assertEqual(("Classification", "Elevation", "Intensity"), modes)

    def test_rgb_requires_all_channels(self):
        self.assertNotIn("RGB", available_attribute_modes(("Red", "Green", "Z")))
        self.assertIn("RGB", available_attribute_modes(("Red", "Green", "Blue")))

    def test_aliased_dimension_satisfies_one_attribute_mode(self):
        modes = available_attribute_modes(("X", "Y", "Z", "ScanAngleRank", "PointSourceID"))
        self.assertIn("Scan Angle", modes)
        self.assertIn("Point Source ID", modes)

    def test_alias_resolution_and_render_state_identity(self):
        self.assertEqual("ScanAngleRank", resolve_attribute("Scan Angle", ("ScanAngleRank",)))
        self.assertIsNone(resolve_attribute("RGB", ("Red", "Green")))
        state = RenderState(color_mode="Elevation", point_size=2)
        self.assertEqual(state.identity(), state.identity())

    def test_bounded_histogram_and_numeric_summary(self):
        result = histogram([0, 1, 2, 3, 4], bins=3)
        self.assertEqual(5, sum(result["bins"]))
        summary = numeric_summary([0, 1, 2, 3, 4])
        self.assertEqual(2.0, summary["median"])
        self.assertEqual(3, summary["p75"])

    def test_nice_ticks_use_readable_intervals(self):
        self.assertIn(nice_tick_step(35), (5.0, 10.0))
        ticks = nice_ticks(12, 18)
        self.assertEqual(ticks, (12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0))

    def test_robust_range_ignores_extreme_values(self):
        result = display_range([0, 1, 2, 3, 4, 1000], mode="ROBUST")
        self.assertLess(result.maximum, 1000)
        self.assertEqual("ROBUST", result.mode)

    def test_manual_range_clamps_values(self):
        result = DisplayRange(0, 10, "MANUAL")
        self.assertEqual(0.0, result.clamp(-3))
        self.assertEqual(10.0, result.clamp(20))

    def test_legend_label_includes_units(self):
        self.assertEqual("Height Above Ground (m)", LegendModel("Height Above Ground", "m").label)


if __name__ == "__main__":
    unittest.main()


class ViewerColorPipelineContractTests(unittest.TestCase):
    def test_viewer_uses_canonical_potree_bindings(self):
        source = (ROOT / "pyforestscan_qgis/viewer/viewer.js").read_text(encoding="utf-8")
        for binding in ('binding:"classification"', 'binding:"intensity"',
                        'binding:"return number"', 'binding:"number of returns"',
                        'binding:"point source id"'):
            self.assertIn(binding, source)
        self.assertIn('script src="visualization_registry.js"',
                      (ROOT / "pyforestscan_qgis/viewer/viewer.html").read_text(encoding="utf-8"))
        self.assertIn('"Height Above Ground": {aliases:', source)
        self.assertIn('cloud.material.extraRange', source)

    def test_renderer_has_distinct_return_and_continuous_intensity_contracts(self):
        source = (ROOT / "pyforestscan_qgis/viewer/assets/build/potree/potree.js").read_text(encoding="utf-8")
        self.assertIn('color = texture2D(gradient, vec2(w, 1.0 - w)).rgb;', source)
        self.assertIn('vec3 getReturnNumber(){ return returnPalette(returnNumber); }', source)
        self.assertIn('vec3 getNumberOfReturns(){ return returnPalette(numberOfReturns); }', source)

    def test_palette_registry_has_scientific_choices_and_stable_unknown_classes(self):
        source = (ROOT / "pyforestscan_qgis/viewer/visualization_registry.js").read_text(encoding="utf-8")
        for name in ("Viridis", "Turbo", "Terrain", "Grayscale", "Heat", "CoolWarm", "Forest"):
            self.assertIn(name, source)
        self.assertIn("function fallback(code)", source)
        self.assertIn("function gradient(name, invert)", source)


from pyforestscan_qgis.core.point_cloud.vertical_selection import (
    HeightRange, VerticalAxis, VerticalSelectionContext,
)

from pyforestscan_qgis.core.point_cloud.scientific_visualization import (
    SPECS, VisualizationKind, available_product_visualizations,
    build_visualization_layer, product_visualization_spec,
)


class ScientificVisualizationContractTests(unittest.TestCase):
    def test_product_specs_are_explicit_and_scientific(self):
        self.assertEqual(VisualizationKind.RASTER_SURFACE, product_visualization_spec("CHM").kind)
        self.assertEqual("height above ground", product_visualization_spec("CHM").vertical_semantics)
        self.assertEqual(9, len(SPECS))

    def test_available_overlays_require_real_outputs(self):
        with self.subTest("missing"):
            self.assertEqual((), available_product_visualizations({"CHM": ROOT / "missing.tif"}))
        output = ROOT / "tests" / "_b2s_chm_test.tif"
        output.write_bytes(b"test")
        try:
            available = available_product_visualizations({"CHM": output, "PAD": output})
            self.assertEqual(("CHM", "PAD"), tuple(item.product_id for item in available))
        finally:
            output.unlink()

    def test_layer_requires_output_and_carries_provenance(self):
        output = ROOT / "tests" / "_b2s_layer_test.tif"
        output.write_bytes(b"test")
        try:
            layer = build_visualization_layer(
                "CHM", output_path=output, source_path="source.laz",
                source_fingerprint="sha256:test", crs="EPSG:32604",
                value_range=(0.0, 42.0), provenance={"engine": "PBM"},
            )
            self.assertEqual("sha256:test", layer.source_fingerprint)
            self.assertEqual("EPSG:32604", layer.crs)
            self.assertEqual("PBM", layer.provenance["engine"])
        finally:
            output.unlink()


from pyforestscan_qgis.core.point_cloud.vertical_selection import (
    HeightRange, VerticalAxis, VerticalSelectionContext,
)


class VerticalSelectionContractTests(unittest.TestCase):
    def test_height_range_is_explicit_about_axis_and_units(self):
        band = HeightRange(12, 13, VerticalAxis.HEIGHT_ABOVE_GROUND)
        self.assertEqual(1.0, band.width)
        self.assertTrue(band.contains(12.5))
        self.assertEqual("height above ground: 12 to 13 source units", band.summary())

    def test_one_unit_band_preserves_axis(self):
        band = HeightRange(4, 9, VerticalAxis.ELEVATION).one_unit_band()
        self.assertEqual((4.0, 5.0), (band.minimum, band.maximum))
        self.assertIs(VerticalAxis.ELEVATION, band.axis)

    def test_context_makes_slice_depth_view_local(self):
        context = VerticalSelectionContext("slice-1", HeightRange(2, 8), 0.5)
        self.assertIn("slice depth: 0.5 XY units", context.summary)
