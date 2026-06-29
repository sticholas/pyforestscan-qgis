"""Deterministic processing time estimates for Mission Control.

Estimates are planning aids only. They intentionally avoid pretending to predict
exact PyForestScan runtime because runtime depends on hardware, storage speed,
point distribution, compression, and QGIS/Python environment state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PRODUCT_COMPLEXITY = {
    "chm": 1.0,
    "canopy_cover": 0.8,
    "pad": 1.8,
    "pai": 1.2,
    "fhd": 1.5,
    "rumple": 0.6,
}


@dataclass(frozen=True)
class ProcessingTimeEstimate:
    """Approximate processing duration for a planned Mission Control job."""

    minimum_seconds: int
    maximum_seconds: int
    confidence: str
    rationale: str
    product_count: int
    point_count: int | None = None
    estimated_cells: int | None = None

    @property
    def display_range(self) -> str:
        """Return a human-readable time range."""
        return f"{_format_duration(self.minimum_seconds)} to {_format_duration(self.maximum_seconds)}"


def estimate_from_plan_file(path: Path | str) -> ProcessingTimeEstimate:
    """Load a Product Planner JSON report and estimate processing time."""
    plan_path = Path(path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source_report = _load_source_report(plan, plan_path.parent)
    return estimate_processing_time(plan, source_report)


def estimate_processing_time(
    product_plan: Mapping[str, Any],
    dataset_report: Mapping[str, Any] | None = None,
) -> ProcessingTimeEstimate:
    """Estimate processing time from a Product Planner report.

    The formula is intentionally simple and deterministic. It scales with the
    number and relative complexity of selected products, point count when known,
    grid cells when known, and height bins for vertical products.
    """
    products = _selected_products(product_plan)
    estimates = product_plan.get("estimates")
    estimates = estimates if isinstance(estimates, Mapping) else {}
    cells = _optional_int(estimates.get("cells"))
    height_bins = _optional_int(estimates.get("height_bins")) or 0
    point_count = _point_count(dataset_report)
    complexity = sum(PRODUCT_COMPLEXITY.get(product, 1.0) for product in products) or 1.0

    seconds = 20.0 + 8.0 * len(products)
    if point_count is not None:
        seconds += (point_count / 1_000_000.0) * 45.0 * complexity
    else:
        seconds += 35.0 * complexity
    if cells is not None:
        seconds += (cells / 1_000_000.0) * 8.0 * complexity
    if height_bins:
        vertical_products = len([product for product in products if product in {"pad", "pai", "fhd"}])
        seconds += height_bins * max(1, vertical_products) * 2.5

    confidence = "low"
    known_parts = []
    if point_count is not None:
        known_parts.append("point count")
    if cells is not None:
        known_parts.append("grid size")
    if point_count is not None and cells is not None:
        confidence = "medium"
    if point_count is not None and cells is not None and products:
        confidence = "medium"
    if point_count is None and cells is None:
        known_parts.append("selected products only")

    minimum = max(10, int(seconds * 0.65))
    maximum = max(minimum + 10, int(seconds * 1.75))
    rationale = (
        "Estimate based on "
        + ", ".join(known_parts)
        + ", selected product count, and relative product complexity. Actual runtime depends on hardware, storage, compression, and data distribution."
    )
    return ProcessingTimeEstimate(
        minimum_seconds=minimum,
        maximum_seconds=maximum,
        confidence=confidence,
        rationale=rationale,
        product_count=len(products),
        point_count=point_count,
        estimated_cells=cells,
    )


def _selected_products(product_plan: Mapping[str, Any]) -> tuple[str, ...]:
    products = product_plan.get("products")
    if not isinstance(products, list):
        return ()
    selected: list[str] = []
    for item in products:
        if not isinstance(item, Mapping) or item.get("requested") is False:
            continue
        product = item.get("product")
        if isinstance(product, str):
            selected.append(product)
    return tuple(selected)


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


def _point_count(dataset_report: Mapping[str, Any] | None) -> int | None:
    if dataset_report is None:
        return None
    point_statistics = dataset_report.get("point_statistics")
    point_statistics = point_statistics if isinstance(point_statistics, Mapping) else {}
    return _optional_int(point_statistics.get("point_count"))


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} sec"
    minutes = round(seconds / 60)
    if minutes < 90:
        return f"{minutes} min"
    hours = minutes / 60
    return f"{hours:.1f} hr"
