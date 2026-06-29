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
    }
)


@dataclass(frozen=True)
class RasterDisplayRange:
    """Display range selected for a generated raster layer."""

    minimum: float
    maximum: float
    source: str
    band: int = 1


def is_raster_result(result_type: str) -> bool:
    """Return whether a job result is a generated raster artifact."""
    return result_type in RASTER_RESULT_TYPES


def layer_display_name(result_type: str, dataset_stem: str | None) -> str:
    """Return a concise generated layer name."""
    product = {
        "chm_geotiff": "CHM",
        "canopy_cover_geotiff": "Canopy Cover",
        "pad_geotiff": "PAD band 1",
        "pai_geotiff": "PAI",
        "fhd_geotiff": "FHD",
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


def apply_grayscale_renderer(layer: Any, result_type: str, *, band: int = 1) -> RasterDisplayRange:
    """Apply grayscale rendering with an explicit min/max contrast range."""
    from qgis.core import QgsContrastEnhancement, QgsSingleBandGrayRenderer

    display_range = qgis_raster_display_range(layer, result_type, band=band)
    provider = layer.dataProvider()
    renderer = QgsSingleBandGrayRenderer(provider, band)
    contrast = QgsContrastEnhancement(provider.dataType(band))
    contrast.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    contrast.setMinimumValue(display_range.minimum)
    contrast.setMaximumValue(display_range.maximum)
    renderer.setContrastEnhancement(contrast)
    layer.setRenderer(renderer)
    _record_display_metadata(layer, display_range)
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


def _record_display_metadata(layer: Any, display_range: RasterDisplayRange) -> None:
    for key, value in (
        ("pyforestscan/display_minimum", display_range.minimum),
        ("pyforestscan/display_maximum", display_range.maximum),
        ("pyforestscan/display_range_source", display_range.source),
        ("pyforestscan/display_band", display_range.band),
    ):
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
