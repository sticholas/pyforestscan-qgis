"""QGIS raster display helpers for generated PyForestScan outputs."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


RASTER_RESULT_TYPES = frozenset(
    {
        "chm_geotiff",
        "canopy_cover_geotiff",
        "pad_geotiff",
        "pai_geotiff",
        "fhd_geotiff",
        "dtm_geotiff",
    }
)


@dataclass(frozen=True)
class RasterDisplayRange:
    """Display range selected for a generated raster layer."""

    minimum: float
    maximum: float
    source: str
    band: int = 1


@dataclass(frozen=True)
class PadRgbBands:
    """Band mapping selected for PAD visualization."""

    red: int
    green: int
    blue: int
    source: str


@dataclass(frozen=True)
class PadRgbDisplay:
    """Display metadata selected for a PAD RGB composite."""

    bands: PadRgbBands
    red_range: RasterDisplayRange
    green_range: RasterDisplayRange
    blue_range: RasterDisplayRange


def is_raster_result(result_type: str) -> bool:
    """Return whether a job result is a generated raster artifact."""
    return result_type in RASTER_RESULT_TYPES


def layer_display_name(result_type: str, dataset_stem: str | None) -> str:
    """Return a concise generated layer name."""
    product = {
        "chm_geotiff": "CHM",
        "canopy_cover_geotiff": "Canopy Cover",
        "pad_geotiff": "PAD RGB 5-3-2",
        "pai_geotiff": "PAI",
        "fhd_geotiff": "FHD",
        "dtm_geotiff": "DTM",
    }.get(result_type, "Raster")
    if dataset_stem:
        return f"PyForestScan {product} - {dataset_stem}"
    return f"PyForestScan {product}"


def safe_display_range(
    result_type: str,
    observed_minimum: float | None,
    observed_maximum: float | None,
    *,
    band: int = 1,
) -> RasterDisplayRange:
    """Return an observed display range or a product-aware fallback."""
    if _valid_range(observed_minimum, observed_maximum):
        return RasterDisplayRange(float(observed_minimum), float(observed_maximum), "observed", band)
    if _single_zero_range(observed_minimum, observed_maximum):
        return RasterDisplayRange(0.0, 0.0, "observed_all_zero", band)
    fallback_minimum, fallback_maximum = _fallback_range(result_type, observed_maximum)
    return RasterDisplayRange(fallback_minimum, fallback_maximum, "fallback", band)


def qgis_raster_display_range(layer: Any, result_type: str, *, band: int = 1) -> RasterDisplayRange:
    """Calculate a safe display range from QGIS raster provider statistics."""
    provider = layer.dataProvider()
    _refresh_provider(layer, provider)
    stats_minimum, stats_maximum = _provider_statistics(provider, layer, band)
    if _valid_range(stats_minimum, stats_maximum):
        return safe_display_range(result_type, stats_minimum, stats_maximum, band=band)

    provider_minimum, provider_maximum = _provider_extent_statistics(provider, band)
    if _valid_range(provider_minimum, provider_maximum):
        return safe_display_range(result_type, provider_minimum, provider_maximum, band=band)

    if _single_zero_range(stats_minimum, stats_maximum) and _single_zero_range(provider_minimum, provider_maximum):
        return safe_display_range(result_type, 0.0, 0.0, band=band)

    observed_maximum = provider_maximum if provider_maximum is not None else stats_maximum
    return safe_display_range(result_type, None, observed_maximum, band=band)


def select_pad_rgb_bands(band_count: int) -> PadRgbBands | None:
    """Return the PAD RGB band mapping for an available band count."""
    if band_count >= 5:
        return PadRgbBands(red=5, green=3, blue=2, source="requested_5_3_2")
    if band_count >= 3:
        return PadRgbBands(red=band_count, green=band_count - 1, blue=max(1, band_count - 2), source="highest_available")
    return None


def apply_generated_raster_renderer(layer: Any, result_type: str) -> RasterDisplayRange | PadRgbDisplay:
    """Apply the default display renderer for a generated raster product."""
    if result_type == "pad_geotiff":
        return apply_pad_renderer(layer)
    return apply_grayscale_renderer(layer, result_type, band=1)


def apply_pad_renderer(layer: Any) -> RasterDisplayRange | PadRgbDisplay:
    """Apply the PAD RGB composite when possible, with grayscale fallback."""
    band_count = _band_count(layer)
    bands = select_pad_rgb_bands(band_count)
    if bands is None:
        display_range = apply_grayscale_renderer(layer, "pad_geotiff", band=1)
        _record_layer_properties(
            layer,
            (
                ("pyforestscan/display_mode", "grayscale"),
                ("pyforestscan/display_fallback", "pad_has_fewer_than_three_bands"),
            ),
        )
        return display_range
    return apply_pad_rgb_renderer(layer, bands)


def apply_pad_rgb_renderer(layer: Any, bands: PadRgbBands) -> PadRgbDisplay:
    """Apply an RGB renderer for PAD using selected height-bin bands."""
    from qgis.core import QgsContrastEnhancement, QgsMultiBandColorRenderer

    provider = layer.dataProvider()
    red_range = qgis_raster_display_range(layer, "pad_geotiff", band=bands.red)
    green_range = qgis_raster_display_range(layer, "pad_geotiff", band=bands.green)
    blue_range = qgis_raster_display_range(layer, "pad_geotiff", band=bands.blue)
    renderer = QgsMultiBandColorRenderer(provider, bands.red, bands.green, bands.blue)
    _set_channel_contrast(renderer, "setRedContrastEnhancement", provider.dataType(bands.red), red_range)
    _set_channel_contrast(renderer, "setGreenContrastEnhancement", provider.dataType(bands.green), green_range)
    _set_channel_contrast(renderer, "setBlueContrastEnhancement", provider.dataType(bands.blue), blue_range)
    layer.setRenderer(renderer)
    _record_pad_rgb_metadata(layer, bands, red_range, green_range, blue_range)
    layer.triggerRepaint()
    return PadRgbDisplay(bands=bands, red_range=red_range, green_range=green_range, blue_range=blue_range)


def apply_grayscale_renderer(layer: Any, result_type: str, *, band: int = 1) -> RasterDisplayRange:
    """Apply grayscale rendering with an explicit min/max contrast range."""
    from qgis.core import QgsSingleBandGrayRenderer

    display_range = qgis_raster_display_range(layer, result_type, band=band)
    provider = layer.dataProvider()
    renderer = QgsSingleBandGrayRenderer(provider, band)
    _set_channel_contrast(renderer, "setContrastEnhancement", provider.dataType(band), display_range)
    layer.setRenderer(renderer)
    _record_grayscale_metadata(layer, display_range)
    layer.triggerRepaint()
    return display_range


def _provider_statistics(provider: Any, layer: Any, band: int) -> tuple[float | None, float | None]:
    try:
        from qgis.core import QgsRasterBandStats

        stats_flag = getattr(QgsRasterBandStats, "All", None)
        if stats_flag is None:
            minimum_flag = getattr(QgsRasterBandStats, "Min", 0)
            maximum_flag = getattr(QgsRasterBandStats, "Max", 0)
            stats_flag = minimum_flag | maximum_flag
        stats = provider.bandStatistics(band, stats_flag, layer.extent(), 0)
        return _stats_values(stats)
    except Exception:  # noqa: BLE001 - provider statistics are best effort.
        return None, None


def _provider_extent_statistics(provider: Any, band: int) -> tuple[float | None, float | None]:
    try:
        minimum = provider.minimumValue(band)
        maximum = provider.maximumValue(band)
        return _finite_or_none(minimum), _finite_or_none(maximum)
    except Exception:  # noqa: BLE001 - provider fallback APIs vary across QGIS builds.
        return None, None


def _refresh_provider(layer: Any, provider: Any) -> None:
    for target, method_name in ((provider, "reloadData"), (layer, "reload")):
        method = getattr(target, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:  # noqa: BLE001 - refresh is helpful but not required.
                pass


def _band_count(layer: Any) -> int:
    for target in (layer, layer.dataProvider()):
        method = getattr(target, "bandCount", None)
        if callable(method):
            try:
                return max(0, int(method()))
            except Exception:  # noqa: BLE001 - provider APIs vary across QGIS builds.
                continue
    return 0


def _set_channel_contrast(renderer: Any, method_name: str, data_type: Any, display_range: RasterDisplayRange) -> None:
    from qgis.core import QgsContrastEnhancement

    method = getattr(renderer, method_name, None)
    if not callable(method):
        return
    contrast = QgsContrastEnhancement(data_type)
    contrast.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    contrast.setMinimumValue(display_range.minimum)
    contrast.setMaximumValue(display_range.maximum)
    method(contrast)


def _record_grayscale_metadata(layer: Any, display_range: RasterDisplayRange) -> None:
    _record_layer_properties(
        layer,
        (
            ("pyforestscan/display_mode", "grayscale"),
            ("pyforestscan/display_minimum", display_range.minimum),
            ("pyforestscan/display_maximum", display_range.maximum),
            ("pyforestscan/display_range_source", display_range.source),
            ("pyforestscan/display_band", display_range.band),
        ),
    )


def _record_pad_rgb_metadata(
    layer: Any,
    bands: PadRgbBands,
    red_range: RasterDisplayRange,
    green_range: RasterDisplayRange,
    blue_range: RasterDisplayRange,
) -> None:
    _record_layer_properties(
        layer,
        (
            ("pyforestscan/display_mode", "rgb"),
            ("pyforestscan/red_band", bands.red),
            ("pyforestscan/green_band", bands.green),
            ("pyforestscan/blue_band", bands.blue),
            ("pyforestscan/pad_rgb_band_source", bands.source),
            ("pyforestscan/red_display_minimum", red_range.minimum),
            ("pyforestscan/red_display_maximum", red_range.maximum),
            ("pyforestscan/green_display_minimum", green_range.minimum),
            ("pyforestscan/green_display_maximum", green_range.maximum),
            ("pyforestscan/blue_display_minimum", blue_range.minimum),
            ("pyforestscan/blue_display_maximum", blue_range.maximum),
        ),
    )


def _record_layer_properties(layer: Any, properties: tuple[tuple[str, object], ...]) -> None:
    for key, value in properties:
        try:
            layer.setCustomProperty(key, value)
        except Exception:  # noqa: BLE001 - metadata should not break rendering.
            return


def _stats_values(stats: Any) -> tuple[float | None, float | None]:
    return _finite_or_none(getattr(stats, "minimumValue", None)), _finite_or_none(getattr(stats, "maximumValue", None))


def _valid_range(minimum: float | None, maximum: float | None) -> bool:
    return minimum is not None and maximum is not None and isfinite(minimum) and isfinite(maximum) and maximum > minimum


def _single_zero_range(minimum: float | None, maximum: float | None) -> bool:
    return minimum == 0 and maximum == 0


def _finite_or_none(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _fallback_range(result_type: str, observed_maximum: float | None) -> tuple[float, float]:
    maximum = _finite_or_none(observed_maximum)
    if maximum is not None and maximum > 0:
        return 0.0, maximum
    if result_type == "canopy_cover_geotiff":
        return 0.0, 1.0
    return 0.0, 1.0
