"""Product Planner models and renderers.

The Product Planner converts a Dataset Explorer JSON report into a documented
processing plan. It does not run PyForestScan calculations, create rasters, or
create scientific products.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Mapping

from .types import ProductType

PRODUCT_LABELS = {
    ProductType.CHM: "Canopy Height Model (CHM)",
    ProductType.PAI: "Plant Area Index (PAI)",
    ProductType.PAD: "Plant Area Density (PAD)",
    ProductType.FHD: "Foliage Height Diversity (FHD)",
    ProductType.CANOPY_COVER: "Canopy Cover",
    ProductType.RUMPLE: "Rumple Index",
}

PRODUCT_OUTPUTS = {
    ProductType.CHM: ("chm.tif", "GeoTIFF raster", "Canopy height raster."),
    ProductType.PAI: ("pai.tif", "GeoTIFF raster", "Future plant area index raster."),
    ProductType.PAD: ("pad_height_bins.tif", "GeoTIFF raster stack", "Future height-binned PAD stack."),
    ProductType.FHD: ("fhd.tif", "GeoTIFF raster", "Future foliage height diversity raster."),
    ProductType.CANOPY_COVER: ("canopy_cover.tif", "GeoTIFF raster", "Canopy cover raster."),
    ProductType.RUMPLE: ("rumple_summary.csv", "CSV table", "Future scalar rumple summary table."),
}


@dataclass(frozen=True)
class PlannerWarning:
    """Product Planner warning or note."""

    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class PlannedOutput:
    """Expected future output for a requested product."""

    product: ProductType
    label: str
    path: Path
    output_type: str
    description: str


@dataclass(frozen=True)
class ProductPlanItem:
    """Planning decision for one requested product."""

    product: ProductType
    label: str
    requested: bool
    feasibility_status: str
    plan_status: str
    reason: str
    warnings: tuple[PlannerWarning, ...]
    outputs: tuple[PlannedOutput, ...]


@dataclass(frozen=True)
class ProductPlannerRequest:
    """Normalized request for Product Planner."""

    explorer_report_path: Path
    requested_products: tuple[ProductType, ...]
    output_folder: Path
    grid_resolution: float
    height_bin_size: float | None = None
    chm_interpolation: str = "linear"
    chm_interpolate_valid_region: bool = False
    chm_clean_edges: bool = False
    chm_output_filename: str = "chm.tif"
    canopy_cover_height_threshold: float = 2.0
    canopy_cover_output_filename: str = "canopy_cover.tif"
    title: str = "PyForestScan Product Planner"
    notes: str = ""


@dataclass(frozen=True)
class ProductPlannerReport:
    """Structured Product Planner report."""

    title: str
    generated_at: str
    source_report: Path
    source_dataset: str | None
    output_folder: Path
    grid_resolution: float
    height_bin_size: float | None
    chm_interpolation: str
    chm_interpolate_valid_region: bool
    chm_clean_edges: bool
    chm_output_filename: str
    canopy_cover_height_threshold: float
    canopy_cover_output_filename: str
    notes: str
    estimated_columns: int | None
    estimated_rows: int | None
    estimated_cells: int | None
    estimated_height_bins: int | None
    products: tuple[ProductPlanItem, ...]
    warnings: tuple[PlannerWarning, ...]
    next_actions: tuple[str, ...]


class ProductPlanError(ValueError):
    """Raised when a Product Planner request or report is invalid."""


def load_dataset_explorer_json(path: Path | str) -> dict[str, Any]:
    """Load a Dataset Explorer JSON report."""
    report_path = Path(path)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProductPlanError(f"Could not read Dataset Explorer JSON report: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProductPlanError(f"Dataset Explorer report is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProductPlanError("Dataset Explorer report JSON must contain an object at the top level.")
    _require_report_sections(payload)
    return payload


def build_product_plan(
    explorer_report: Mapping[str, Any],
    request: ProductPlannerRequest,
) -> ProductPlannerReport:
    """Build a product plan from a Dataset Explorer report and user request."""
    if not request.requested_products:
        raise ProductPlanError("At least one desired product must be selected.")
    if request.grid_resolution <= 0:
        raise ProductPlanError("Grid resolution must be greater than zero.")
    if request.height_bin_size is not None and request.height_bin_size <= 0:
        raise ProductPlanError("Height bin size must be greater than zero when provided.")
    _validate_chm_parameters(request)
    _validate_canopy_cover_parameters(request)

    feasibility = _feasibility_by_product(explorer_report)
    dataset_warnings = _dataset_warnings(explorer_report)
    columns, rows, cells = _estimate_grid(explorer_report, request.grid_resolution)
    height_bins = _estimate_height_bins(explorer_report, request.height_bin_size)

    global_warnings = list(dataset_warnings)
    global_warnings.extend(_chm_planning_warnings(explorer_report, request))
    if cells is None:
        global_warnings.append(
            PlannerWarning(
                "GRID_ESTIMATE_UNAVAILABLE",
                "WARNING",
                "Bounds are missing or invalid, so grid size could not be estimated.",
            )
        )
    if request.height_bin_size is None and ProductType.PAD in request.requested_products:
        global_warnings.append(
            PlannerWarning(
                "PAD_HEIGHT_BIN_SIZE_MISSING",
                "WARNING",
                "PAD was requested without a height bin size; choose a bin size before processing.",
            )
        )

    products = tuple(
        _build_plan_item(product, feasibility, request.output_folder, request.chm_output_filename, request.canopy_cover_output_filename)
        for product in request.requested_products
    )
    next_actions = _next_actions(products, tuple(global_warnings))

    return ProductPlannerReport(
        title=request.title or "PyForestScan Product Planner",
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_report=request.explorer_report_path,
        source_dataset=_source_dataset(explorer_report),
        output_folder=request.output_folder,
        grid_resolution=request.grid_resolution,
        height_bin_size=request.height_bin_size,
        chm_interpolation=request.chm_interpolation,
        chm_interpolate_valid_region=request.chm_interpolate_valid_region,
        chm_clean_edges=request.chm_clean_edges,
        chm_output_filename=request.chm_output_filename,
        canopy_cover_height_threshold=request.canopy_cover_height_threshold,
        canopy_cover_output_filename=request.canopy_cover_output_filename,
        notes=request.notes,
        estimated_columns=columns,
        estimated_rows=rows,
        estimated_cells=cells,
        estimated_height_bins=height_bins,
        products=products,
        warnings=tuple(global_warnings),
        next_actions=next_actions,
    )


def plan_to_dict(report: ProductPlannerReport) -> dict[str, Any]:
    """Convert a Product Planner report to a JSON-serializable dictionary."""
    return {
        "title": report.title,
        "generated_at": report.generated_at,
        "source_report": str(report.source_report),
        "source_dataset": report.source_dataset,
        "output_folder": str(report.output_folder),
        "parameters": {
            "grid_resolution": report.grid_resolution,
            "height_bin_size": report.height_bin_size,
            "chm_interpolation": report.chm_interpolation,
            "chm_interpolate_valid_region": report.chm_interpolate_valid_region,
            "chm_clean_edges": report.chm_clean_edges,
            "chm_output_filename": report.chm_output_filename,
            "canopy_cover_height_threshold": report.canopy_cover_height_threshold,
            "canopy_cover_output_filename": report.canopy_cover_output_filename,
        },
        "estimates": {
            "columns": report.estimated_columns,
            "rows": report.estimated_rows,
            "cells": report.estimated_cells,
            "height_bins": report.estimated_height_bins,
        },
        "notes": report.notes,
        "warnings": [
            {"code": warning.code, "severity": warning.severity, "message": warning.message}
            for warning in report.warnings
        ],
        "products": [
            {
                "product": item.product.value,
                "label": item.label,
                "requested": item.requested,
                "feasibility_status": item.feasibility_status,
                "plan_status": item.plan_status,
                "reason": item.reason,
                "warnings": [
                    {"code": warning.code, "severity": warning.severity, "message": warning.message}
                    for warning in item.warnings
                ],
                "estimated_outputs": [
                    {
                        "path": str(output.path),
                        "type": output.output_type,
                        "description": output.description,
                    }
                    for output in item.outputs
                ],
            }
            for item in report.products
        ],
        "next_actions": list(report.next_actions),
        "processing_executed": False,
    }


def render_plan_json(report: ProductPlannerReport) -> str:
    """Render Product Planner JSON."""
    return json.dumps(plan_to_dict(report), indent=2, sort_keys=True)


def write_plan_json(report: ProductPlannerReport, output_path: Path | str) -> Path:
    """Write Product Planner JSON."""
    path = Path(output_path)
    _ensure_parent(path)
    path.write_text(render_plan_json(report) + "\n", encoding="utf-8")
    return path


def write_plan_csv(report: ProductPlannerReport, output_path: Path | str) -> Path:
    """Write Product Planner CSV."""
    path = Path(output_path)
    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("section", "product", "name", "value", "status", "message"))
        writer.writerow(("dataset", "", "source_report", str(report.source_report), "", ""))
        writer.writerow(("dataset", "", "source_dataset", report.source_dataset or "Unknown", "", ""))
        writer.writerow(("parameters", "", "grid_resolution", report.grid_resolution, "", ""))
        writer.writerow(("parameters", "", "height_bin_size", report.height_bin_size or "", "", ""))
        writer.writerow(("parameters", "", "chm_interpolation", report.chm_interpolation, "", ""))
        writer.writerow(("parameters", "", "chm_interpolate_valid_region", report.chm_interpolate_valid_region, "", ""))
        writer.writerow(("parameters", "", "chm_clean_edges", report.chm_clean_edges, "", ""))
        writer.writerow(("parameters", "", "chm_output_filename", report.chm_output_filename, "", ""))
        writer.writerow(("parameters", "", "canopy_cover_height_threshold", report.canopy_cover_height_threshold, "", ""))
        writer.writerow(("parameters", "", "canopy_cover_output_filename", report.canopy_cover_output_filename, "", ""))
        writer.writerow(("estimate", "", "columns", report.estimated_columns or "", "", ""))
        writer.writerow(("estimate", "", "rows", report.estimated_rows or "", "", ""))
        writer.writerow(("estimate", "", "cells", report.estimated_cells or "", "", ""))
        writer.writerow(("estimate", "", "height_bins", report.estimated_height_bins or "", "", ""))
        for warning in report.warnings:
            writer.writerow(("warning", "", warning.code, "", warning.severity, warning.message))
        for item in report.products:
            writer.writerow(("product", item.product.value, item.label, item.reason, item.plan_status, ""))
            for warning in item.warnings:
                writer.writerow(("product_warning", item.product.value, warning.code, "", warning.severity, warning.message))
            for output in item.outputs:
                writer.writerow(("output", item.product.value, output.output_type, str(output.path), item.plan_status, output.description))
        for action in report.next_actions:
            writer.writerow(("next_action", "", "action", "", "", action))
    return path


def render_plan_html(report: ProductPlannerReport) -> str:
    """Render a browser-friendly Product Planner HTML report."""
    product_cards = "".join(_product_card_html(item) for item in report.products)
    warnings = "".join(
        f'<li class="{escape(warning.severity.lower())}"><strong>{escape(warning.code)}</strong>: {escape(warning.message)}</li>'
        for warning in report.warnings
    ) or '<li class="ok">No planner warnings.</li>'
    actions = "".join(f"<li>{escape(action)}</li>" for action in report.next_actions)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(report.title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; color: #1f2933; background: #f7f9fb; }}
    header {{ background: #25424a; color: #fff; padding: 28px 36px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px 24px 48px; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }}
    .panel, .product {{ background: #fff; border: 1px solid #d8e0e6; border-radius: 6px; padding: 18px; margin-bottom: 16px; }}
    .ready {{ border-left: 5px solid #247a3d; }}
    .needs-review {{ border-left: 5px solid #b7791f; }}
    .blocked {{ border-left: 5px solid #b83232; }}
    .status {{ font-weight: 700; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border-bottom: 1px solid #d8e0e6; padding: 9px 10px; text-align: left; }}
    th {{ background: #edf3f5; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(report.title)}</h1>
    <p>Dataset: {escape(report.source_dataset or 'Unknown')}</p>
    <p>Generated {escape(report.generated_at)}</p>
  </header>
  <main>
    <section class="panel">
      <h2>Plan Parameters</h2>
      <table>
        <tr><th>Output folder</th><td>{escape(str(report.output_folder))}</td></tr>
        <tr><th>Grid resolution</th><td>{report.grid_resolution:g}</td></tr>
        <tr><th>Height bin size</th><td>{_format_optional_number(report.height_bin_size)}</td></tr>
        <tr><th>CHM interpolation</th><td>{escape(report.chm_interpolation)}</td></tr>
        <tr><th>CHM interpolate valid region</th><td>{str(report.chm_interpolate_valid_region)}</td></tr>
        <tr><th>CHM clean edges</th><td>{str(report.chm_clean_edges)}</td></tr>
        <tr><th>CHM output filename</th><td>{escape(report.chm_output_filename)}</td></tr>
        <tr><th>Canopy cover height threshold</th><td>{report.canopy_cover_height_threshold:g}</td></tr>
        <tr><th>Canopy cover output filename</th><td>{escape(report.canopy_cover_output_filename)}</td></tr>
        <tr><th>Estimated grid</th><td>{_format_grid(report)}</td></tr>
        <tr><th>Estimated height bins</th><td>{report.estimated_height_bins if report.estimated_height_bins is not None else 'Unknown'}</td></tr>
      </table>
    </section>
    <section>
      <h2>Requested Products</h2>
      <div class="grid">{product_cards}</div>
    </section>
    <section class="panel">
      <h2>Warnings</h2>
      <ul>{warnings}</ul>
    </section>
    <section class="panel">
      <h2>Recommended Next Actions</h2>
      <ul>{actions}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_plan_html(report: ProductPlannerReport, output_path: Path | str) -> Path:
    """Write Product Planner HTML."""
    path = Path(output_path)
    _ensure_parent(path)
    path.write_text(render_plan_html(report), encoding="utf-8")
    return path


def _require_report_sections(payload: Mapping[str, Any]) -> None:
    for key in ("dataset", "geometry", "point_statistics", "supported_products"):
        if key not in payload:
            raise ProductPlanError(f"Dataset Explorer report is missing required section: {key}")


def _validate_chm_parameters(request: ProductPlannerRequest) -> None:
    """Validate CHM-specific planning parameters."""
    allowed_interpolation = {"linear", "nearest", "cubic"}
    if request.chm_interpolation not in allowed_interpolation:
        raise ProductPlanError("CHM interpolation must be linear, nearest, or cubic.")
    output_name = Path(request.chm_output_filename)
    if output_name.name != request.chm_output_filename or output_name.suffix.lower() not in {".tif", ".tiff"}:
        raise ProductPlanError("CHM output filename must be a simple .tif or .tiff filename.")


def _validate_canopy_cover_parameters(request: ProductPlannerRequest) -> None:
    """Validate canopy-cover-specific planning parameters."""
    if request.canopy_cover_height_threshold < 0:
        raise ProductPlanError("Canopy cover height threshold must be zero or greater.")
    output_name = Path(request.canopy_cover_output_filename)
    if output_name.name != request.canopy_cover_output_filename or output_name.suffix.lower() not in {".tif", ".tiff"}:
        raise ProductPlanError("Canopy cover output filename must be a simple .tif or .tiff filename.")


def _chm_planning_warnings(explorer_report: Mapping[str, Any], request: ProductPlannerRequest) -> list[PlannerWarning]:
    """Return CHM readiness warnings that should travel with the plan."""
    if ProductType.CHM not in request.requested_products:
        return []
    warnings: list[PlannerWarning] = []
    point_statistics = explorer_report.get("point_statistics")
    point_statistics = point_statistics if isinstance(point_statistics, Mapping) else {}
    dimensions = set(str(value) for value in point_statistics.get("dimensions", []) if value)
    if "HeightAboveGround" not in dimensions:
        warnings.append(
            PlannerWarning(
                "CHM_HAG_FROM_PDAL",
                "WARNING",
                "HeightAboveGround is not present in the source dimensions; CHM processing will request PDAL height normalization.",
            )
        )
    classification_entries = point_statistics.get("classification_summary")
    has_ground = False
    if isinstance(classification_entries, list):
        for item in classification_entries:
            if isinstance(item, dict) and int(item.get("classification", -1)) == 2 and int(item.get("count", 0)) > 0:
                has_ground = True
    if not has_ground:
        warnings.append(
            PlannerWarning(
                "CHM_GROUND_REVIEW",
                "WARNING",
                "Ground class 2 was not confirmed; review height normalization and CHM values after processing.",
            )
        )
    point_count = point_statistics.get("point_count")
    if isinstance(point_count, int) and point_count > 5_000_000:
        warnings.append(
            PlannerWarning(
                "CHM_LARGE_POINT_COUNT",
                "WARNING",
                "This dataset has more than 5 million points; Phase 10B CHM processing is not tiled and may be slow or memory intensive.",
            )
        )
    source_dataset = _source_dataset(explorer_report)
    if source_dataset:
        try:
            source_path = Path(source_dataset)
            if source_path.is_file() and source_path.stat().st_size > 1_000_000_000:
                warnings.append(
                    PlannerWarning(
                        "CHM_LARGE_FILE",
                        "WARNING",
                        "The source point-cloud file is larger than 1 GB; test CHM processing on a small dataset before larger production runs.",
                    )
                )
        except OSError:
            pass
    return warnings


def _feasibility_by_product(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    products = report.get("supported_products", [])
    if not isinstance(products, list):
        raise ProductPlanError("Dataset Explorer supported_products section must be a list.")
    by_product: dict[str, Mapping[str, Any]] = {}
    for item in products:
        if isinstance(item, Mapping) and item.get("product"):
            by_product[str(item["product"])] = item
    return by_product


def _dataset_warnings(report: Mapping[str, Any]) -> tuple[PlannerWarning, ...]:
    warnings = []
    raw_warnings = report.get("warnings", [])
    if isinstance(raw_warnings, list):
        for item in raw_warnings:
            if not isinstance(item, Mapping):
                continue
            warnings.append(
                PlannerWarning(
                    str(item.get("code", "DATASET_WARNING")),
                    str(item.get("severity", "WARNING")),
                    str(item.get("message", "Dataset Explorer reported a warning.")),
                )
            )
    return tuple(warnings)


def _source_dataset(report: Mapping[str, Any]) -> str | None:
    dataset = report.get("dataset", {})
    if isinstance(dataset, Mapping):
        value = dataset.get("source_path")
        return str(value) if value else None
    return None


def _estimate_grid(report: Mapping[str, Any], resolution: float) -> tuple[int | None, int | None, int | None]:
    geometry = report.get("geometry", {})
    bounds = geometry.get("bounds") if isinstance(geometry, Mapping) else None
    if not isinstance(bounds, Mapping):
        return (None, None, None)
    try:
        width = float(bounds["max_x"]) - float(bounds["min_x"])
        height = float(bounds["max_y"]) - float(bounds["min_y"])
    except (KeyError, TypeError, ValueError):
        return (None, None, None)
    if width <= 0 or height <= 0:
        return (None, None, None)
    columns = max(1, math.ceil(width / resolution))
    rows = max(1, math.ceil(height / resolution))
    return (columns, rows, columns * rows)


def _estimate_height_bins(report: Mapping[str, Any], height_bin_size: float | None) -> int | None:
    if height_bin_size is None:
        return None
    geometry = report.get("geometry", {})
    height_range = geometry.get("height_range") if isinstance(geometry, Mapping) else None
    if not isinstance(height_range, Mapping):
        return None
    try:
        minimum = float(height_range["minimum"])
        maximum = float(height_range["maximum"])
    except (KeyError, TypeError, ValueError):
        return None
    if maximum <= minimum:
        return None
    return max(1, math.ceil((maximum - minimum) / height_bin_size))


def _build_plan_item(
    product: ProductType,
    feasibility: Mapping[str, Mapping[str, Any]],
    output_folder: Path,
    chm_output_filename: str = "chm.tif",
    canopy_cover_output_filename: str = "canopy_cover.tif",
) -> ProductPlanItem:
    label = PRODUCT_LABELS[product]
    raw = feasibility.get(product.value)
    warnings: list[PlannerWarning] = []
    if raw is None:
        status = "Unavailable"
        reason = "Dataset Explorer did not report feasibility for this product."
        plan_status = "Blocked"
        warnings.append(PlannerWarning("PRODUCT_NOT_IN_EXPLORER_REPORT", "ERROR", reason))
    else:
        status = str(raw.get("status", "Unavailable"))
        reason = str(raw.get("reason", "No feasibility reason was provided."))
        plan_status = _plan_status_from_feasibility(status)
        if status == "Unavailable":
            warnings.append(PlannerWarning("PRODUCT_UNAVAILABLE", "ERROR", reason))
        elif status == "Warning":
            warnings.append(PlannerWarning("PRODUCT_NEEDS_REVIEW", "WARNING", reason))
    outputs = _planned_outputs(product, output_folder, chm_output_filename, canopy_cover_output_filename) if plan_status != "Blocked" else ()
    return ProductPlanItem(
        product=product,
        label=label,
        requested=True,
        feasibility_status=status,
        plan_status=plan_status,
        reason=reason,
        warnings=tuple(warnings),
        outputs=outputs,
    )


def _plan_status_from_feasibility(status: str) -> str:
    normalized = status.lower()
    if normalized == "available":
        return "Ready"
    if normalized == "warning":
        return "Needs review"
    return "Blocked"


def _planned_outputs(product: ProductType, output_folder: Path, chm_output_filename: str = "chm.tif", canopy_cover_output_filename: str = "canopy_cover.tif") -> tuple[PlannedOutput, ...]:
    filename, output_type, description = PRODUCT_OUTPUTS[product]
    if product is ProductType.CHM:
        filename = chm_output_filename
    elif product is ProductType.CANOPY_COVER:
        filename = canopy_cover_output_filename
    output = PlannedOutput(
        product=product,
        label=PRODUCT_LABELS[product],
        path=output_folder / filename,
        output_type=output_type,
        description=description,
    )
    metadata = PlannedOutput(
        product=product,
        label=PRODUCT_LABELS[product],
        path=output_folder / f"{product.value}_metadata.json",
        output_type="JSON metadata",
        description="Future provenance and processing metadata.",
    )
    return (output, metadata)


def _next_actions(
    products: tuple[ProductPlanItem, ...],
    warnings: tuple[PlannerWarning, ...],
) -> tuple[str, ...]:
    actions = ["Review this plan before running future scientific processing."]
    if any(item.plan_status == "Blocked" for item in products):
        actions.append("Resolve blocked products before running a processing batch.")
    if any(item.plan_status == "Needs review" for item in products):
        actions.append("Review warnings and missing prerequisites before processing products marked Needs review.")
    if any(warning.severity.upper() == "ERROR" for warning in warnings):
        actions.append("Resolve Dataset Explorer errors before product generation.")
    if all(item.plan_status == "Ready" for item in products):
        actions.append("Requested products are ready for future processing implementation once scientific workflows are available.")
    actions.append("No PyForestScan calculations were run by this planner.")
    return tuple(actions)


def _product_card_html(item: ProductPlanItem) -> str:
    css = item.plan_status.lower().replace(" ", "-")
    outputs = "".join(f"<li>{escape(str(output.path))}</li>" for output in item.outputs) or "<li>No outputs planned.</li>"
    warnings = "".join(f"<li>{escape(warning.message)}</li>" for warning in item.warnings)
    warning_block = f"<ul>{warnings}</ul>" if warnings else "<p>No product warnings.</p>"
    return (
        f'<section class="product {escape(css)}">'
        f'<h3>{escape(item.label)}</h3>'
        f'<p class="status">{escape(item.plan_status)}</p>'
        f'<p>{escape(item.reason)}</p>'
        f'<h4>Estimated outputs</h4><ul>{outputs}</ul>'
        f'<h4>Warnings</h4>{warning_block}'
        '</section>'
    )


def _format_grid(report: ProductPlannerReport) -> str:
    if report.estimated_columns is None or report.estimated_rows is None or report.estimated_cells is None:
        return "Unknown"
    return f"{report.estimated_columns:,} columns x {report.estimated_rows:,} rows ({report.estimated_cells:,} cells)"


def _format_optional_number(value: float | None) -> str:
    return "Not specified" if value is None else f"{value:g}"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
