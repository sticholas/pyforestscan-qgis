"""Tests for QGIS-free raster styling decisions."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.ui.raster_styling import layer_display_name, qgis_raster_display_range, safe_display_range, select_pad_default_slice_band, select_pad_rgb_bands


class RasterStylingTests(unittest.TestCase):
    """Verify display-range decisions that do not require QGIS."""

    def test_observed_nonzero_range_is_used(self) -> None:
        """A real provider min/max range is preserved for display."""
        display_range = safe_display_range("chm_geotiff", 0.25, 37.5)

        self.assertEqual(0.25, display_range.minimum)
        self.assertEqual(37.5, display_range.maximum)
        self.assertEqual("observed", display_range.source)

    def test_zero_zero_range_is_preserved_when_observed(self) -> None:
        """All-zero rasters are the only case allowed to keep a 0/0 range."""
        display_range = safe_display_range("pai_geotiff", 0.0, 0.0)

        self.assertEqual(0.0, display_range.minimum)
        self.assertEqual(0.0, display_range.maximum)
        self.assertEqual("observed_all_zero", display_range.source)

    def test_canopy_cover_falls_back_to_unit_interval(self) -> None:
        """Canopy cover uses a product-aware 0..1 fallback when stats are unavailable."""
        display_range = safe_display_range("canopy_cover_geotiff", None, None)

        self.assertEqual(0.0, display_range.minimum)
        self.assertEqual(1.0, display_range.maximum)
        self.assertEqual("fallback", display_range.source)

    def test_positive_provider_max_is_kept_when_minimum_is_missing(self) -> None:
        """Partial provider stats still avoid a blank 0/0 contrast range."""
        display_range = safe_display_range("fhd_geotiff", None, 2.75)

        self.assertEqual(0.0, display_range.minimum)
        self.assertEqual(2.75, display_range.maximum)
        self.assertEqual("fallback", display_range.source)


    def test_qgis_range_uses_provider_min_max_when_statistics_import_is_unavailable(self) -> None:
        """Provider min/max fallback is used without requiring QGIS in tests."""
        layer = _FakeLayer(_FakeProvider(1.25, 9.5))

        display_range = qgis_raster_display_range(layer, "chm_geotiff")

        self.assertEqual(1.25, display_range.minimum)
        self.assertEqual(9.5, display_range.maximum)
        self.assertEqual("observed", display_range.source)

    def test_pad_layer_name_defaults_to_height_slice(self) -> None:
        """PAD is named as a representative height slice, not an authoritative RGB metric."""
        self.assertEqual("PyForestScan PAD height slice - tile_001", layer_display_name("pad_geotiff", "tile_001"))
        self.assertEqual("PyForestScan PAD height composite 5/3/2 - tile_001", layer_display_name("pad_composite_geotiff", "tile_001"))

    def test_pad_default_slice_band_is_representative_and_bounded(self) -> None:
        self.assertEqual(select_pad_default_slice_band(20), 10)
        self.assertEqual(select_pad_default_slice_band(4), 4)

    def test_pad_rgb_bands_use_requested_mapping_when_available(self) -> None:
        """PAD uses red 5, green 3, blue 2 when at least five bands exist."""
        bands = select_pad_rgb_bands(8)

        self.assertIsNotNone(bands)
        assert bands is not None
        self.assertEqual((5, 3, 2), (bands.red, bands.green, bands.blue))
        self.assertEqual("requested_5_3_2", bands.source)

    def test_pad_rgb_bands_use_highest_available_fallback(self) -> None:
        """PAD uses a descending RGB composite when fewer than five bands exist."""
        bands = select_pad_rgb_bands(4)

        self.assertIsNotNone(bands)
        assert bands is not None
        self.assertEqual((4, 3, 2), (bands.red, bands.green, bands.blue))
        self.assertEqual("highest_available", bands.source)

    def test_pad_rgb_bands_return_none_for_grayscale_fallback(self) -> None:
        """PAD falls back to grayscale when an RGB composite is not possible."""
        self.assertIsNone(select_pad_rgb_bands(2))


class _FakeProvider:
    def __init__(self, minimum: float | None, maximum: float | None) -> None:
        self._minimum = minimum
        self._maximum = maximum

    def minimumValue(self, band: int) -> float | None:
        return self._minimum

    def maximumValue(self, band: int) -> float | None:
        return self._maximum


class _FakeLayer:
    def __init__(self, provider: _FakeProvider) -> None:
        self._provider = provider

    def dataProvider(self) -> _FakeProvider:
        return self._provider

    def extent(self) -> object:
        return object()


if __name__ == "__main__":
    unittest.main()
