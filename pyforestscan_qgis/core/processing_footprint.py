"""Processing footprint summaries for Mission Control.

Footprints describe expected output size and raster shape. They intentionally do
not predict runtime because runtime depends on machine, storage speed, point
density, compression, and product selection.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

BYTES_PER_FLOAT32_CELL = 4
SINGLE_BAND_PRODUCTS = {"chm", "canopy_cover", "pai", "fhd"}
MINIMAL_PRODUCTS = {"rumple"}


@dataclass(frozen=True)
class ProductFootprint:
    """Estimated output footprint for one selected product."""

    product: str
    label: str
    bands: int
    estimated_bytes: int
    storage_note: str


@dataclass(frozen=True)
class ProcessingFootprint:
    """Estimated storage and raster footprint for a planned job."""

    selected_products: tuple[str, ...]
    output_folder: Path | None
    columns: int | None
    rows: int | None
    cells: int | None
    height_bins: int | None
    total_bands: int
    estimated_bytes: int
    product_footprints: tuple[ProductFootprint, ...]
    confidence: str
    caveat: str
    warnings: tuple[str, ...] = ()

    @property
    def display_storage(self) -> str:
        """Return human-readable estimated storage."""
        return _format_bytes(self.estimated_bytes)

    @property
    def display_dimensions(self) -> str:
        """Return human-readable raster dimensions."""
        if self.columns is None or self.rows is None:
            return "Unknown"
        return f"{self.columns:,} columns x {self.rows:,} rows"


def footprint_from_plan_file(path: Path | str) -> ProcessingFootprint:
    """Load a Product Planner JSON report and estimate processing footprint."""
    plan_path = Path(path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source_report = _load_source_report(plan, plan_path.parent)
    return estimate_processing_footprint(plan, source_report)


def estimate_processing_footprint(
    product_plan: Mapping[str, Any],
    dataset_report: Mapping[str, Any] | None = None,
) -> ProcessingFootprint:
    """Estimate output storage, raster dimensions, and band counts."""
    products = _selected_products(product_plan)
    parameters = product_plan.get("parameters")
    parameters = parameters if isinstance(parameters, Mapping) else {}
    estimates = product_plan.get("estimates")
    estimates = estimates if isinstance(estimates, Mapping) else {}
    columns = _optional_int(estimates.get("columns"))
    rows = _optional_int(estimates.get("rows"))
    cells = _optional_int(estimates.get("cells"))
    height_bins = _optional_int(estimates.get("height_bins"))

    if cells is None:
        columns, rows, cells = _estimate_cells_from_bounds(dataset_report, parameters)
    if cells is None and columns is not None and rows is not None:
        cells = columns * rows

    output_folder = _optional_path(product_plan.get("output_folder"))
    product_footprints = tuple(_product_footprint(product, cells, height_bins) for product in products)
    total_bytes = sum(item.estimated_bytes for item in product_footprints)
    total_bands = sum(item.bands for item in product_footprints)
    confidence = "medium" if cells is not None else "low"
    warnings = _large_job_warnings(total_bytes, cells, total_bands)
    return ProcessingFootprint(
        selected_products=tuple(item.label for item in product_footprints),
        output_folder=output_folder,
        columns=columns,
        rows=rows,
        cells=cells,
        height_bins=height_bins,
        total_bands=total_bands,
        estimated_bytes=total_bytes,
        product_footprints=product_footprints,
        confidence=confidence,
        caveat="Storage estimate assumes float32 rasters at 4 bytes per cell before GeoTIFF compression. Processing time depends on machine, storage speed, point density, and product selection.",
        warnings=warnings,
    )


def _selected_products(product_plan: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    products = product_plan.get("products")
    if not isinstance(products, list):
        return ()
    selected: list[Mapping[str, Any]] = []
    for item in products:
        if not isinstance(item, Mapping) or item.get("requested") is False:
            continue
        selected.append(item)
    return tuple(selected)


def _product_footprint(product_item: Mapping[str, Any], cells: int | None, height_bins: int | None) -> ProductFootprint:
    product = str(product_item.get("product") or "unknown")
    label = str(product_item.get("label") or product)
    if product == "pad":
        bands = max(1, height_bins or 1)
    elif product in MINIMAL_PRODUCTS:
        bands = 0
    else:
        bands = 1 if product in SINGLE_BAND_PRODUCTS else 1
    bytes_estimate = 0 if product in MINIMAL_PRODUCTS or cells is None else cells * bands * BYTES_PER_FLOAT32_CELL
    note = "Minimal CSV/table output" if product in MINIMAL_PRODUCTS else f"{bands} band{'s' if bands != 1 else ''} x float32"
    return ProductFootprint(product, label, bands, bytes_estimate, note)


def _estimate_cells_from_bounds(
    dataset_report: Mapping[str, Any] | None,
    parameters: Mapping[str, Any],
) -> tuple[int | None, int | None, int | None]:
    if dataset_report is None:
        return None, None, None
    resolution = _optional_float(parameters.get("grid_resolution"))
    if resolution is None or resolution <= 0:
        return None, None, None
    geometry = dataset_report.get("geometry")
    geometry = geometry if isinstance(geometry, Mapping) else {}
    bounds = geometry.get("bounds")
    bounds = bounds if isinstance(bounds, Mapping) else {}
    min_x = _optional_float(bounds.get("min_x"))
    max_x = _optional_float(bounds.get("max_x"))
    min_y = _optional_float(bounds.get("min_y"))
    max_y = _optional_float(bounds.get("max_y"))
    if None in (min_x, max_x, min_y, max_y):
        return None, None, None
    width = max(0.0, float(max_x) - float(min_x))
    height = max(0.0, float(max_y) - float(min_y))
    if width <= 0 or height <= 0:
        return None, None, None
    columns = max(1, math.ceil(width / resolution))
    rows = max(1, math.ceil(height / resolution))
    return columns, rows, columns * rows


def _load_source_report(product_plan: Mapping[str, Any], base: Path) -> Mapping[str, Any] | None:
    source = product_plan.get("source_report")
    if not isinstance(source, str) or not source.strip():
        return None
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = base / source_path
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _large_job_warnings(total_bytes: int, cells: int | None, bands: int) -> tuple[str, ...]:
    warnings: list[str] = []
    if total_bytes >= 1_000_000_000:
        warnings.append("Large output footprint: estimated raster storage is at least 1 GB before compression.")
    if cells is not None and cells >= 100_000_000:
        warnings.append("Large raster grid: estimated cell count is at least 100 million cells.")
    if bands >= 30:
        warnings.append("Large band count: PAD or combined outputs may create many raster bands.")
    return tuple(warnings)


def _optional_path(value: object) -> Path | None:
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_bytes(value: int) -> str:
    if value < 1_000_000:
        return f"{value / 1_000:.1f} KB"
    if value < 1_000_000_000:
        return f"{value / 1_000_000:.1f} MB"
    return f"{value / 1_000_000_000:.2f} GB"
