"""Dataset Explorer report normalization for the knowledge engine."""

from __future__ import annotations

from typing import Any, Mapping

from .types import DatasetFacts


def facts_from_dataset_explorer_report(report: Mapping[str, Any]) -> DatasetFacts:
    """Extract normalized facts from a Dataset Explorer JSON dictionary."""
    dataset = _mapping(report.get("dataset"))
    geometry = _mapping(report.get("geometry"))
    point_statistics = _mapping(report.get("point_statistics"))
    bounds = _mapping(geometry.get("bounds")) if geometry.get("bounds") is not None else {}
    classification_summary = point_statistics.get("classification_summary", [])
    return DatasetFacts(
        source_path=_optional_string(dataset.get("source_path")),
        point_count=_optional_int(point_statistics.get("point_count")),
        estimated_density=_optional_float(geometry.get("estimated_density_points_per_square_unit")),
        area=_area(bounds),
        crs=_optional_string(geometry.get("crs")),
        dimensions=tuple(str(item) for item in point_statistics.get("dimensions", []) if item is not None),
        classification_counts=_classification_counts(classification_summary),
        warnings=tuple(item for item in report.get("warnings", []) if isinstance(item, Mapping)),
        supported_products=tuple(item for item in report.get("supported_products", []) if isinstance(item, Mapping)),
        dataset_size_bytes=_optional_int(dataset.get("size_bytes")),
    )


def is_geographic_crs(crs: str | None) -> bool:
    """Return a conservative guess about whether a CRS has angular units."""
    if not crs:
        return False
    lowered = crs.lower()
    return "epsg:4326" in lowered or "geogcs" in lowered or 'unit["degree"' in lowered or "degree" in lowered


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _area(bounds: Mapping[str, Any]) -> float | None:
    min_x = _optional_float(bounds.get("min_x"))
    max_x = _optional_float(bounds.get("max_x"))
    min_y = _optional_float(bounds.get("min_y"))
    max_y = _optional_float(bounds.get("max_y"))
    if None in (min_x, max_x, min_y, max_y):
        return None
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _classification_counts(summary: object) -> dict[int, int]:
    counts: dict[int, int] = {}
    if not isinstance(summary, list):
        return counts
    for item in summary:
        if not isinstance(item, Mapping):
            continue
        code = _optional_int(item.get("classification"))
        count = _optional_int(item.get("count"))
        if code is not None and count is not None:
            counts[code] = count
    return counts


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
