"""Dataset Explorer report models and renderers.

This module converts adapter dataset inspection results into planning reports. It
does not call PyForestScan calculations, create rasters, or generate scientific
products.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from .types import Bounds3D, ClassificationCount, DatasetInspection, ProductType

LOW_DENSITY_THRESHOLD = 1.0
GROUND_CLASSIFICATION = 2
VEGETATION_CLASSIFICATIONS = (3, 4, 5)
SUPPORTED_LAS_POINT_FORMATS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}


@dataclass(frozen=True)
class DatasetWarning:
    """User-facing dataset warning with a stable code and severity."""

    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class ProductFeasibility:
    """Planning status for a future PyForestScan product."""

    product: ProductType
    label: str
    status: str
    reason: str


@dataclass(frozen=True)
class DatasetExplorerReport:
    """Structured Dataset Explorer report returned by the planning workflow."""

    title: str
    generated_at: str
    source_path: str
    source_format: str
    is_remote: bool
    metadata_source: str
    point_count: int | None
    bounds: Bounds3D | None
    crs: str | None
    point_format: str | None
    dimensions: tuple[str, ...]
    classification_summary: tuple[ClassificationCount, ...]
    estimated_density: float | None
    height_range: tuple[float | None, float | None]
    has_color: bool
    has_gps_time: bool
    has_intensity: bool
    warnings: tuple[DatasetWarning, ...]
    products: tuple[ProductFeasibility, ...]
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)


def build_dataset_explorer_report(
    inspection: DatasetInspection,
    title: str = "PyForestScan Dataset Explorer",
) -> DatasetExplorerReport:
    """Build a typed Dataset Explorer report from adapter inspection output."""
    dimensions = tuple(inspection.dimensions)
    dimension_names = {dimension.lower() for dimension in dimensions}
    classification_map = {
        item.classification: item.count for item in inspection.classification_summary
    }
    has_classification_dimension = "classification" in dimension_names
    has_classification_summary = bool(classification_map)
    has_ground = classification_map.get(GROUND_CLASSIFICATION, 0) > 0
    has_vegetation = any(classification_map.get(code, 0) > 0 for code in VEGETATION_CLASSIFICATIONS)
    has_hag = _has_any_dimension(dimension_names, "heightaboveground", "hag")
    has_z = "z" in dimension_names
    has_color = _has_color_dimensions(dimension_names)
    has_gps_time = _has_any_dimension(dimension_names, "gpstime", "gps time", "gps_time")
    has_intensity = "intensity" in dimension_names
    bounds = inspection.bounds
    height_range = _height_range(bounds)

    warnings = _build_warnings(
        inspection=inspection,
        has_classification_dimension=has_classification_dimension,
        has_classification_summary=has_classification_summary,
        has_ground=has_ground,
        has_vegetation=has_vegetation,
        has_hag=has_hag,
        has_z=has_z,
        has_color=has_color,
        has_gps_time=has_gps_time,
        has_intensity=has_intensity,
    )
    products = _build_product_feasibility(
        has_hag=has_hag,
        has_z=has_z,
        has_ground=has_ground,
        has_vegetation=has_vegetation,
        has_classification_summary=has_classification_summary,
    )
    actions = _recommended_actions(warnings, products)

    return DatasetExplorerReport(
        title=title,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_path=str(inspection.source.path),
        source_format=inspection.source.format.value,
        is_remote=inspection.source.is_remote,
        metadata_source=inspection.metadata_source,
        point_count=inspection.point_count,
        bounds=bounds,
        crs=inspection.crs,
        point_format=inspection.point_format,
        dimensions=dimensions,
        classification_summary=inspection.classification_summary,
        estimated_density=inspection.estimated_density,
        height_range=height_range,
        has_color=has_color,
        has_gps_time=has_gps_time,
        has_intensity=has_intensity,
        warnings=warnings,
        products=products,
        recommended_actions=actions,
    )


def report_to_dict(report: DatasetExplorerReport) -> dict[str, Any]:
    """Convert a report to a JSON-serializable dictionary."""
    return {
        "title": report.title,
        "generated_at": report.generated_at,
        "dataset": {
            "source_path": report.source_path,
            "format": report.source_format,
            "is_remote": report.is_remote,
            "metadata_source": report.metadata_source,
        },
        "geometry": {
            "bounds": _bounds_to_dict(report.bounds),
            "crs": report.crs,
            "estimated_density_points_per_square_unit": report.estimated_density,
            "height_range": {
                "minimum": report.height_range[0],
                "maximum": report.height_range[1],
            },
        },
        "point_statistics": {
            "point_count": report.point_count,
            "point_format": report.point_format,
            "dimensions": list(report.dimensions),
            "classification_summary": [
                {"classification": item.classification, "count": item.count}
                for item in report.classification_summary
            ],
            "has_color": report.has_color,
            "has_gps_time": report.has_gps_time,
            "has_intensity": report.has_intensity,
        },
        "warnings": [
            {"code": warning.code, "severity": warning.severity, "message": warning.message}
            for warning in report.warnings
        ],
        "supported_products": [
            {
                "product": product.product.value,
                "label": product.label,
                "status": product.status,
                "reason": product.reason,
            }
            for product in report.products
        ],
        "recommended_actions": list(report.recommended_actions),
    }


def render_json_report(report: DatasetExplorerReport) -> str:
    """Render the report as stable, human-readable JSON."""
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True)


def write_json_report(report: DatasetExplorerReport, output_path: Path | str) -> Path:
    """Write a JSON Dataset Explorer report."""
    path = Path(output_path)
    _ensure_parent(path)
    path.write_text(render_json_report(report) + "\n", encoding="utf-8")
    return path


def write_csv_summary(report: DatasetExplorerReport, output_path: Path | str) -> Path:
    """Write a long-form CSV summary suitable for loading as a QGIS table."""
    path = Path(output_path)
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("section", "name", "value", "status", "message"))
        for row in _csv_rows(report):
            writer.writerow(row)
    return path


def render_html_report(report: DatasetExplorerReport) -> str:
    """Render a browser-friendly HTML Dataset Explorer report."""
    warning_items = "".join(
        f'<li class="{escape(warning.severity.lower())}"><strong>{escape(warning.code)}</strong>: '
        f'{escape(warning.message)}</li>'
        for warning in report.warnings
    ) or '<li class="ok">No warnings detected.</li>'
    product_cards = "".join(
        f'<section class="product {escape(product.status.lower())}">'
        f'<h3>{escape(product.label)}</h3>'
        f'<p class="status">{escape(product.status)}</p>'
        f'<p>{escape(product.reason)}</p>'
        '</section>'
        for product in report.products
    )
    classification_chart = _classification_chart_html(report.classification_summary)
    actions = "".join(f"<li>{escape(action)}</li>" for action in report.recommended_actions)
    bounds = _format_bounds(report.bounds)
    dimensions = ", ".join(escape(item) for item in report.dimensions) or "None reported"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(report.title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; color: #1f2933; background: #f7f9fb; }}
    header {{ background: #163b3d; color: #fff; padding: 28px 36px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px 24px 48px; }}
    h1, h2, h3 {{ margin-top: 0; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    .panel, .product {{ background: #fff; border: 1px solid #d8e0e6; border-radius: 6px; padding: 18px; margin-bottom: 16px; }}
    .metric {{ font-size: 1.5rem; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border-bottom: 1px solid #d8e0e6; padding: 9px 10px; text-align: left; }}
    th {{ background: #edf3f5; }}
    .bar {{ display: flex; align-items: center; gap: 10px; margin: 8px 0; }}
    .bar span {{ min-width: 58px; }}
    .bar div {{ height: 14px; background: #2d7c83; border-radius: 3px; }}
    .available {{ border-left: 5px solid #247a3d; }}
    .warning {{ border-left: 5px solid #b7791f; }}
    .unavailable, .error {{ border-left: 5px solid #b83232; }}
    .ok {{ color: #247a3d; }}
    .status {{ font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }}
    code {{ background: #eef2f4; padding: 2px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(report.title)}</h1>
    <p>{escape(report.source_path)}</p>
    <p>Generated {escape(report.generated_at)}</p>
  </header>
  <main>
    <section class="grid">
      <div class="panel"><h2>Point Count</h2><p class="metric">{escape(_format_number(report.point_count))}</p></div>
      <div class="panel"><h2>Density</h2><p class="metric">{escape(_format_float(report.estimated_density))}</p></div>
      <div class="panel"><h2>CRS</h2><p>{escape(report.crs or 'Unknown')}</p></div>
      <div class="panel"><h2>Format</h2><p>{escape(report.source_format.upper())}</p></div>
    </section>

    <section class="panel">
      <h2>Dataset Metadata</h2>
      <table>
        <tr><th>Metadata source</th><td>{escape(report.metadata_source)}</td></tr>
        <tr><th>Point format</th><td>{escape(report.point_format or 'Unknown')}</td></tr>
        <tr><th>Bounds</th><td>{escape(bounds)}</td></tr>
        <tr><th>Height range</th><td>{escape(_format_height_range(report.height_range))}</td></tr>
        <tr><th>Dimensions</th><td>{dimensions}</td></tr>
        <tr><th>Color</th><td>{'Yes' if report.has_color else 'No'}</td></tr>
        <tr><th>GPS time</th><td>{'Yes' if report.has_gps_time else 'No'}</td></tr>
        <tr><th>Intensity</th><td>{'Yes' if report.has_intensity else 'No'}</td></tr>
      </table>
    </section>

    <section class="panel">
      <h2>Classification Summary</h2>
      {classification_chart}
    </section>

    <section>
      <h2>Supported PyForestScan Products</h2>
      <div class="grid">{product_cards}</div>
    </section>

    <section class="panel">
      <h2>Warnings</h2>
      <ul>{warning_items}</ul>
    </section>

    <section class="panel">
      <h2>Recommended Next Actions</h2>
      <ul>{actions}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_html_report(report: DatasetExplorerReport, output_path: Path | str) -> Path:
    """Write a browser-friendly HTML Dataset Explorer report."""
    path = Path(output_path)
    _ensure_parent(path)
    path.write_text(render_html_report(report), encoding="utf-8")
    return path


def _build_warnings(
    inspection: DatasetInspection,
    has_classification_dimension: bool,
    has_classification_summary: bool,
    has_ground: bool,
    has_vegetation: bool,
    has_hag: bool,
    has_z: bool,
    has_color: bool,
    has_gps_time: bool,
    has_intensity: bool,
) -> tuple[DatasetWarning, ...]:
    warnings: list[DatasetWarning] = []
    for index, message in enumerate(inspection.warnings, start=1):
        warnings.append(DatasetWarning(f"ADAPTER_WARNING_{index}", "WARNING", message))
    if not inspection.crs:
        warnings.append(DatasetWarning("UNKNOWN_CRS", "WARNING", "Coordinate reference system is unknown."))
    if not has_classification_dimension:
        warnings.append(DatasetWarning("MISSING_CLASSIFICATION_DIMENSION", "WARNING", "Classification dimension was not reported."))
    elif not has_classification_summary:
        warnings.append(DatasetWarning("MISSING_CLASSIFICATION_SUMMARY", "WARNING", "Classification counts are not available from inspection."))
    if has_classification_summary and not has_ground:
        warnings.append(DatasetWarning("NO_GROUND_CLASS", "WARNING", "Ground class 2 was not detected."))
    if has_classification_summary and not has_vegetation:
        warnings.append(DatasetWarning("NO_VEGETATION_CLASSES", "WARNING", "Vegetation classes 3, 4, or 5 were not detected."))
    if not has_hag and not has_z:
        warnings.append(DatasetWarning("NO_HEIGHT_DIMENSION", "ERROR", "Neither HeightAboveGround nor Z was reported."))
    elif not has_hag:
        warnings.append(DatasetWarning("NO_HEIGHT_ABOVE_GROUND", "WARNING", "HeightAboveGround is not present; future products will need HAG generation."))
    if not has_color:
        warnings.append(DatasetWarning("NO_COLOR", "WARNING", "RGB color dimensions were not detected."))
    if not has_gps_time:
        warnings.append(DatasetWarning("NO_GPS_TIME", "WARNING", "GPS time dimension was not detected."))
    if not has_intensity:
        warnings.append(DatasetWarning("NO_INTENSITY", "WARNING", "Intensity dimension was not detected."))
    if _point_format_is_unsupported(inspection.point_format):
        warnings.append(DatasetWarning("UNSUPPORTED_POINT_FORMAT", "WARNING", f"Point format {inspection.point_format} is not in the known LAS 0-10 range."))
    if inspection.estimated_density is not None and inspection.estimated_density < LOW_DENSITY_THRESHOLD:
        warnings.append(DatasetWarning("LOW_POINT_DENSITY", "WARNING", "Estimated point density is below 1 point per square unit."))
    return tuple(warnings)


def _build_product_feasibility(
    has_hag: bool,
    has_z: bool,
    has_ground: bool,
    has_vegetation: bool,
    has_classification_summary: bool,
) -> tuple[ProductFeasibility, ...]:
    height_ready = has_hag or (has_z and (has_ground or not has_classification_summary))
    height_reason = _height_reason(has_hag, has_z, has_ground, has_classification_summary)
    vegetation_note = " Vegetation classes were detected." if has_vegetation else " Vegetation classes were not confirmed."

    products = []
    for product, label in (
        (ProductType.CHM, "Canopy Height Model (CHM)"),
        (ProductType.PAI, "Plant Area Index (PAI)"),
        (ProductType.PAD, "Plant Area Density (PAD)"),
        (ProductType.FHD, "Foliage Height Diversity (FHD)"),
        (ProductType.CANOPY_COVER, "Canopy Cover"),
        (ProductType.RUMPLE, "Rumple Index"),
    ):
        if not height_ready:
            products.append(ProductFeasibility(product, label, "Unavailable", height_reason))
        elif has_hag and (has_vegetation or not has_classification_summary):
            products.append(ProductFeasibility(product, label, "Available", height_reason + vegetation_note))
        else:
            products.append(ProductFeasibility(product, label, "Warning", height_reason + vegetation_note))
    return tuple(products)


def _height_reason(
    has_hag: bool,
    has_z: bool,
    has_ground: bool,
    has_classification_summary: bool,
) -> str:
    if has_hag:
        return "HeightAboveGround is present for height-based products."
    if has_z and has_ground:
        return "Z and ground class 2 are present; future HAG generation appears feasible."
    if has_z and not has_classification_summary:
        return "Z is present, but classifications were not confirmed; future HAG setup must be validated."
    if has_z:
        return "Z is present, but no ground class was detected for HAG generation."
    return "No usable height dimension was detected."


def _recommended_actions(
    warnings: tuple[DatasetWarning, ...],
    products: tuple[ProductFeasibility, ...],
) -> tuple[str, ...]:
    warning_codes = {warning.code for warning in warnings}
    actions = ["Review the JSON report and keep it with project metadata."]
    if "UNKNOWN_CRS" in warning_codes:
        actions.append("Confirm or assign the dataset CRS before running product workflows.")
    if "NO_HEIGHT_ABOVE_GROUND" in warning_codes:
        actions.append("Plan a height-above-ground step using ground class or a DTM before CHM and metric generation.")
    if "NO_GROUND_CLASS" in warning_codes:
        actions.append("Classify ground points or provide an external DTM before height-based products.")
    if "MISSING_CLASSIFICATION_SUMMARY" in warning_codes:
        actions.append("Run a sampled or full classification inspection before committing to production processing.")
    if all(product.status == "Available" for product in products):
        actions.append("Dataset appears ready for the future CHM workflow once processing is implemented.")
    else:
        actions.append("Resolve warnings marked above before treating product feasibility as final.")
    return tuple(actions)


def _csv_rows(report: DatasetExplorerReport) -> tuple[tuple[str, str, str, str, str], ...]:
    rows: list[tuple[str, str, str, str, str]] = [
        ("dataset", "source_path", report.source_path, "", ""),
        ("dataset", "format", report.source_format, "", ""),
        ("dataset", "metadata_source", report.metadata_source, "", ""),
        ("geometry", "crs", report.crs or "Unknown", "", ""),
        ("geometry", "bounds", _format_bounds(report.bounds), "", ""),
        ("statistics", "point_count", _format_number(report.point_count), "", ""),
        ("statistics", "point_format", report.point_format or "Unknown", "", ""),
        ("statistics", "estimated_density", _format_float(report.estimated_density), "", ""),
        ("statistics", "height_range", _format_height_range(report.height_range), "", ""),
        ("dimensions", "present", "; ".join(report.dimensions), "", ""),
        ("dimensions", "color", str(report.has_color), "", ""),
        ("dimensions", "gps_time", str(report.has_gps_time), "", ""),
        ("dimensions", "intensity", str(report.has_intensity), "", ""),
    ]
    for item in report.classification_summary:
        rows.append(("classification", str(item.classification), str(item.count), "", ""))
    for warning in report.warnings:
        rows.append(("warning", warning.code, "", warning.severity, warning.message))
    for product in report.products:
        rows.append(("product", product.label, product.product.value, product.status, product.reason))
    for action in report.recommended_actions:
        rows.append(("recommended_action", "action", "", "", action))
    return tuple(rows)


def _classification_chart_html(summary: tuple[ClassificationCount, ...]) -> str:
    if not summary:
        return "<p>No classification counts available.</p>"
    max_count = max(item.count for item in summary) or 1
    bars = []
    for item in summary:
        width = max(2, int((item.count / max_count) * 100))
        bars.append(
            f'<div class="bar"><span>{item.classification}</span>'
            f'<div style="width:{width}%"></div><strong>{item.count}</strong></div>'
        )
    return "".join(bars)


def _bounds_to_dict(bounds: Bounds3D | None) -> dict[str, float | None] | None:
    if bounds is None:
        return None
    return {
        "min_x": bounds.min_x,
        "max_x": bounds.max_x,
        "min_y": bounds.min_y,
        "max_y": bounds.max_y,
        "min_z": bounds.min_z,
        "max_z": bounds.max_z,
    }


def _format_bounds(bounds: Bounds3D | None) -> str:
    if bounds is None:
        return "Unknown"
    return (
        f"X {bounds.min_x:g} to {bounds.max_x:g}; "
        f"Y {bounds.min_y:g} to {bounds.max_y:g}; "
        f"Z {_format_optional_float(bounds.min_z)} to {_format_optional_float(bounds.max_z)}"
    )


def _height_range(bounds: Bounds3D | None) -> tuple[float | None, float | None]:
    if bounds is None:
        return (None, None)
    return (bounds.min_z, bounds.max_z)


def _format_height_range(height_range: tuple[float | None, float | None]) -> str:
    return f"{_format_optional_float(height_range[0])} to {_format_optional_float(height_range[1])}"


def _format_optional_float(value: float | None) -> str:
    return "Unknown" if value is None else f"{value:g}"


def _format_float(value: float | None) -> str:
    return "Unknown" if value is None else f"{value:.3f}"


def _format_number(value: int | None) -> str:
    return "Unknown" if value is None else f"{value:,}"


def _has_color_dimensions(dimensions: set[str]) -> bool:
    return {"red", "green", "blue"}.issubset(dimensions)


def _has_any_dimension(dimensions: set[str], *names: str) -> bool:
    normalized = {name.lower().replace("_", "").replace(" ", "") for name in names}
    compact_dimensions = {dimension.lower().replace("_", "").replace(" ", "") for dimension in dimensions}
    return bool(normalized.intersection(compact_dimensions))


def _point_format_is_unsupported(point_format: str | None) -> bool:
    if point_format is None:
        return False
    try:
        return int(point_format) not in SUPPORTED_LAS_POINT_FORMATS
    except ValueError:
        return True


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
